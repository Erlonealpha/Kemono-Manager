import asyncio
from collections import deque
from typing import Union, Optional, NewType, Any

from kemonobakend.kemono.builtins import get_sha256_from_path
from kemonobakend.session_pool import SessionPool
from kemonobakend.utils.ext import AsyncIOScheduler

from .types import (
    DownloadInfo, DownloadProperties, DownloadResult, DownloadStatus, ProgressTracker, AutoList, DownloadWaiter,
    TaskId
)
from .download import DownloadTask
from kemonobakend.log import logger

class StopTask:
    def __init__(self):
        self.priority = -float("inf")
    def __lt__(self, other):
        return self.priority < other.priority


class Downloader_Dev:
    download_tasks: dict[TaskId, DownloadTask] = {}
    tasks:          dict[TaskId, asyncio.Task] = {}
    running_tasks:   dict[TaskId, asyncio.Task] = {}
    _looper_task = None
    
    def __init__(
        self,
        prop: DownloadProperties = None,
        loop: asyncio.AbstractEventLoop = None,
    ):
        self._loop = loop
        self.prop = prop or DownloadProperties()
        self.tasks_queue: asyncio.PriorityQueue[DownloadTask] = asyncio.PriorityQueue(self.prop.max_tasks_concurrent)
        self.semaphore = asyncio.Semaphore(self.prop.max_tasks_concurrent)
        self.is_running = False
        self.task_ready_event = asyncio.Event()
        self.stop_event = asyncio.Event()
        # self.scheduler = AsyncIOScheduler()
        self._running_main_task: Optional[asyncio.Task] = None
        self._done_waiters: list[DownloadWaiter] = []
        self._put_waiters: list[DownloadWaiter] = []
        self._done_waiters_map: dict[TaskId, asyncio.Future] = {}
        self._put_waiters_map: dict[TaskId, asyncio.Future] = {}
        self._lock = asyncio.Lock()
    
    def start(self):
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        self._running_main_task = self._loop.create_task(self._start())
        return self._running_main_task
    
    async def _start(self):
        if self.is_running:
            return
        # self.scheduler.start()
        self._looper_task = self._loop.create_task(self.looper())
        self.is_running = True
        await asyncio.wait_for(self._looper_task, timeout=None)
    
    async def stop(self):
        self.stop_event.set()
        self.is_running = False
        # if self.tasks_queue.empty(): # no tasks in queue, stop immediately
        await self.tasks_queue.put(StopTask())
        await self.clear_waiters()

    async def create_task(
        self,
        url: str,
        save_path: str,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        file_sha256: Optional[str] = None,
        start: bool = True,
        priority: int = 0,
        json: Optional[Union[dict, list]]=None,
        headers: Optional[dict] = None,
        cookies: Optional[Union[dict, str]] = None,
    ) -> TaskId:
        if file_sha256 is None:
            file_sha256 = get_sha256_from_path(url)
        if file_name is None:
            file_name = url.split("/")[-1]
        
        info = DownloadInfo(
            url=url,
            file_name=file_name,
            save_path=save_path,
            file_sha256=file_sha256,
            file_size=file_size,
            json=json,
            headers=headers,
            cookies=cookies,
        )
        task = DownloadTask(info, self.prop, start=start, priority=priority)
        await self._put_download_task(task)
        return task.task_id
    
    async def looper(self):
        async def callback_wrap(coro, task_id: TaskId):
            async with self.semaphore:
                try:
                    result = await coro
                except asyncio.CancelledError as e:
                    logger.exception(e)
                    self.prop.progress_tracker.on_cancel(task_id)
                except Exception as e:
                    logger.exception(e)
                    self.prop.progress_tracker.on_error(task_id, e)
                else:
                    self.prop.progress_tracker.on_complete(task_id, result)
                finally:
                    self._loop.create_task(self._clean_task(task_id, locals().get("result")))
        
        while not self.stop_event.is_set():
            if len(self.running_tasks) >= self.prop.max_tasks_concurrent:
                await self.task_ready_event.wait()
                self.task_ready_event.clear()

            download_task = await self.tasks_queue.get()
            if isinstance(download_task, StopTask):
                break

            task = self._loop.create_task(
                callback_wrap(download_task.start(), download_task.task_id),
                name=f"Task {download_task.task_id} {download_task.info.file_name}"
            )
            await self._put_task(download_task.task_id, task)
            self.task_ready_event.set()
    
    async def _clean_task(self, task_id: TaskId, result: Any):
        try:
            if result:
                download_task: DownloadTask = self.download_tasks[task_id]
                logger.info(f"Task {task_id} {download_task.info.file_name} download success")
            else:
                logger.info(f"Task {task_id} download failed {result}")
        except Exception as e:
            logger.warning(f"Error during task cleanup for {task_id}: {e}")
        finally:
            self.prop.progress_tracker.advance_main()
            self.running_tasks.pop(task_id, None)
            await self._wakeup_waiter(self._done_waiters_map, task_id)
            await self._wakeup_waiter(self._done_waiters)

    
    async def _put_download_task(self, task: DownloadTask):
        async with self._lock:
            self.download_tasks[task.task_id] = task
            await self.tasks_queue.put(task)
    
    async def _put_task(self, task_id: TaskId, task: asyncio.Task):
        self.tasks[task_id] = task
        self.running_tasks[task_id] = task
        await self._wakeup_waiter(self._put_waiters_map, task_id)
        await self._wakeup_waiter(self._put_waiters)
        self.task_ready_event.set()
    
    async def cancel_task(self, task_id: TaskId, accept_wait: bool = False):
        if task := self.tasks.get(task_id):
            if task.done():
                return
            task.cancel()
        elif accept_wait:
            task = await self._wait_for_get_task(task_id)
            if not task.done():
                task.cancel()
    
    
    async def wait_forever(self):
        '''Wait for looper run forever until stop event is set or KeyboardInterrupt is raised.'''
        await asyncio.wait_for(self._running_main_task, timeout=None)
    
    async def wait_for_task(self, task_id: TaskId, timeout: Optional[float] = None) -> DownloadResult:
        task = self.tasks.get(task_id)
        if task is None:
            task = await self._wait_for_get_task(task_id, timeout=timeout)
        return await asyncio.wait_for(task, timeout=timeout)

    async def wait_any_tasks_done(self, count: int = 1, timeout: Optional[float] = None):
        if count <= 0:
            return
        waiter = await self._register_waiter_list(self._done_waiters, count)
        try:
            await asyncio.wait_for(waiter, timeout=timeout)
        except:
            waiter.cancel()
            try:
                self._done_waiters.remove(waiter)
            except:
                pass
            raise

    async def _wakeup_waiter(self, waiters: Union[list[DownloadWaiter], dict[TaskId, asyncio.Future]], task_id: TaskId = None):
        # if not self._lock.locked():
        #     await self._lock.acquire()
        if isinstance(waiters, dict):
            waiter = waiters.pop(task_id, None)
            if waiter and not waiter.done():
                waiter.set_result(None)
        elif isinstance(waiters, list):
            i = len(waiters) - 1
            while i >= 0:
                waiter = waiters[i]
                if waiter.count == 1:
                    waiters.pop(i)
                else:
                    waiter.count -= 1
                if not waiter.waiter.done():
                    waiter.waiter.set_result(None)
                i -= 1
        # if self._lock.locked():
        #     self._lock.release()
    
    async def _wait_for_get_task(self, task_id: TaskId, timeout: Optional[float] = None):
        waiter = await self._register_waiter_map(self._put_waiters_map, task_id)
        try:
            await asyncio.wait_for(waiter, timeout=timeout)
        except:
            waiter.cancel()
            try:
                self._put_waiters_map.pop(task_id)
            except:
                pass
            raise
        return self.running_tasks.pop(task_id)
    
    async def _register_waiter_map(self, waiter_map: dict[TaskId, asyncio.Future], task_id: TaskId):
        async with self._lock:
            if task_id not in waiter_map:
                waiter_map[task_id] = self._loop.create_future()
            return waiter_map[task_id]
    
    async def _register_waiter_list(self, waiter_list: list[DownloadWaiter], count: int = 1):
        async with self._lock:
            for waiter in waiter_list:
                if waiter.count == count:
                    return waiter.waiter
            waiter = self._loop.create_future()
            waiter_list.append(DownloadWaiter(waiter, count))
            return waiter
    
    async def clear_waiters(self):
        async with self._lock:
            for waiter in self._done_waiters:
                waiter.waiter.cancel()
            for waiter in self._put_waiters:
                waiter.waiter.cancel()
            for waiter in self._done_waiters_map.values():
                waiter.cancel()
            for waiter in self._put_waiters_map.values():
                waiter.cancel()
            self._done_waiters.clear()
            self._put_waiters.clear()
            self._done_waiters_map.clear()
            self._put_waiters_map.clear()
            logger.debug("Waiters cleared")


    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


class Downloader:
    download_tasks: dict[TaskId, DownloadTask] = {}
    tasks:          dict[TaskId, asyncio.Task] = {}
    running_tasks:   dict[TaskId, asyncio.Task] = {}
    _looper_task = None
    
    def __init__(
        self,
        prop: DownloadProperties = None,
        loop: asyncio.AbstractEventLoop = None,
    ):
        self._loop = loop
        self.prop = prop or DownloadProperties()
        self.tasks_queue: asyncio.PriorityQueue[DownloadTask] = asyncio.PriorityQueue(self.prop.max_tasks_concurrent)
        self.semaphore = asyncio.Semaphore(self.prop.max_tasks_concurrent)
        self.is_running = False
        self.stop_event = asyncio.Event()
        # self.scheduler = AsyncIOScheduler()
        self._running_main_task: Optional[asyncio.Task] = None
        self._done_waiters: list[DownloadWaiter] = []
        self._put_waiters: list[DownloadWaiter] = []
        self._done_waiters_map: dict[TaskId, asyncio.Future] = {}
        self._put_waiters_map: dict[TaskId, asyncio.Future] = {}
        self._lock = asyncio.Lock()
    
    def start(self):
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        self._running_main_task = self._loop.create_task(self._start())
        return self._running_main_task
    
    async def _start(self):
        if self.is_running:
            return
        # self.scheduler.start()
        self._looper_task = self._loop.create_task(self.looper())
        self.is_running = True
        await asyncio.wait_for(self._looper_task, timeout=None)
    
    async def stop(self):
        self.stop_event.set()
        self.is_running = False
        # if self.tasks_queue.empty(): # no tasks in queue, stop immediately
        await self.tasks_queue.put(StopTask())
        await self.clear_waiters()
    
    async def looper(self):
        async def callback_wrap(coro, task_id: TaskId):
            async with self.semaphore:
                try:
                    result = await coro
                except asyncio.CancelledError:
                    logger.info(f"Task {task_id} cancelled")
                    self.prop.progress_tracker.on_cancel(task_id)
                except Exception as e:
                    logger.error(f"Task {task_id} error: {e}")
                    self.prop.progress_tracker.on_error(task_id, e)
                else:
                    self.prop.progress_tracker.on_complete(task_id, result)
                finally:
                    if locals().get("result", None) is not None:
                        if result:
                            download_task: DownloadTask = self.download_tasks[task_id]
                            logger.info(f"Task {task_id} {download_task.info.file_name} download success")
                        else:
                            logger.info(f"Task {task_id} download failed {result}")
                    else:
                        pass
                    self.prop.progress_tracker.advance_main()
                    self.running_tasks.pop(task_id)
                    # await self._wakeup_waiter(self._done_waiters_map, task_id)
                    # await self._wakeup_waiter(self._done_waiters)
        
        while not self.stop_event.is_set():
            try:
                if len(self.running_tasks) >= self.prop.max_tasks_concurrent:
                    continue
                download_task = await self.tasks_queue.get()
                if isinstance(download_task, StopTask):
                    break
                task = self._loop.create_task(callback_wrap(download_task.start(), download_task.task_id), name=f"Task {download_task.task_id} {download_task.info.file_name}")
                await self._put_task(download_task.task_id, task)
            except KeyboardInterrupt:
                break
            finally:
                await asyncio.sleep(1)

    async def create_task(
        self,
        url: str,
        save_path: str,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        file_sha256: Optional[str] = None,
        start: bool = True,
        priority: int = 0,
        json: Optional[Union[dict, list]]=None,
        headers: Optional[dict] = None,
        cookies: Optional[Union[dict, str]] = None,
    ) -> TaskId:
        if file_sha256 is None:
            file_sha256 = get_sha256_from_path(url)
        if file_name is None:
            file_name = url.split("/")[-1]
        
        info = DownloadInfo(
            url=url,
            file_name=file_name,
            save_path=save_path,
            file_sha256=file_sha256,
            file_size=file_size,
            json=json,
            headers=headers,
            cookies=cookies,
        )
        task = DownloadTask(info, self.prop, start=start, priority=priority)
        await self._put_download_task(task)
        return task.task_id
    
    async def _put_download_task(self, task: DownloadTask):
        async with self._lock:
            self.download_tasks[task.task_id] = task
            await self.tasks_queue.put(task)
    
    async def _put_task(self, task_id: TaskId, task: asyncio.Task):
        self.tasks[task_id] = task
        self.running_tasks[task_id] = task
        # await self._wakeup_waiter(self._put_waiters_map, task_id)
        # await self._wakeup_waiter(self._put_waiters)
    
    async def cancel_task(self, task_id: TaskId, accept_wait: bool = False):
        if task := self.tasks.get(task_id):
            if task.done():
                return
            task.cancel()
        elif accept_wait:
            task = await self._wait_for_get_task(task_id)
            if not task.done():
                task.cancel()
    
    async def wait_forever(self):
        '''Wait for looper run forever until stop event is set or KeyboardInterrupt is raised.'''
        await asyncio.wait_for(self._running_main_task, timeout=None)
    
    async def wait_for_task(self, task_id: TaskId, timeout: Optional[float] = None) -> DownloadResult:
        task = self.tasks.get(task_id)
        if task is None:
            task = await self._wait_for_get_task(task_id, timeout=timeout)
        return await asyncio.wait_for(task, timeout=timeout)

    async def wait_any_tasks_done(self, count: int = 1, timeout: Optional[float] = None):
        if count <= 0:
            return
        waiter = await self._register_waiter_list(self._done_waiters, count)
        try:
            await asyncio.wait_for(waiter, timeout=timeout)
        except:
            waiter.cancel()
            try:
                self._done_waiters.remove(waiter)
            except:
                pass
            raise

    async def _wakeup_waiter(self, waiters: Union[list[DownloadWaiter], dict[TaskId, asyncio.Future]], task_id: TaskId = None):
        while waiters:
            if isinstance(waiters, dict):
                waiters_ = [waiters.pop(task_id, None)]
            elif isinstance(waiters, list):
                waiters_ = []
                for i in range(len(waiters)-1, -1, -1):
                    if waiters[i].count == 1:
                        waiters.pop(i)
                    waiters[i].count -= 1
                    waiters_.append(waiters[i])
            
            for waiter in waiters_:
                if waiter is not None and not waiter.done():
                    waiter.set_result(None)
    
    async def _wait_for_get_task(self, task_id: TaskId, timeout: Optional[float] = None):
        waiter = await self._register_waiter_map(self._put_waiters_map, task_id)
        try:
            await asyncio.wait_for(waiter, timeout=timeout)
        except:
            waiter.cancel()
            try:
                self._put_waiters_map.pop(task_id)
            except:
                pass
            raise
        return self.running_tasks.pop(task_id)
    
    async def _register_waiter_map(self, waiter_map: dict[TaskId, asyncio.Future], task_id: TaskId):
        async with self._lock:
            if task_id in waiter_map:
                return waiter_map[task_id]
            waiter = self._loop.create_future()
            waiter_map[task_id] = waiter
    
    async def _register_waiter_list(self, waiter_list: list[DownloadWaiter], count: int = 1):
        async with self._lock:
            try:
                if i := waiter_list.index(count) is not None:
                    return waiter_list[i].waiter
            except ValueError:
                pass
            waiter = self._loop.create_future()
            waiter_list.append(DownloadWaiter(waiter, count))
            return waiter
    
    async def clear_waiters(self):
        async with self._lock:
            for waiter in self._done_waiters:
                waiter.waiter.cancel()
            for waiter in self._put_waiters:
                waiter.waiter.cancel()
            for waiter in self._done_waiters_map.values():
                waiter.cancel()
            for waiter in self._put_waiters_map.values():
                waiter.cancel()
            self._done_waiters.clear()
            self._put_waiters.clear()
            self._done_waiters_map.clear()
            self._put_waiters_map.clear()


    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()