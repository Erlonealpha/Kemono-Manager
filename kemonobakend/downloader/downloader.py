import asyncio
import signal
from typing import Union, Optional, NewType, Any

from kemonobakend.kemono.builtins import get_sha256_from_path
from kemonobakend.log import logger

from .types import (
    DownloadInfo, DownloadProperties, DownloadResult, DownloadStatus, ProgressTracker, AutoList, DownloadWaiter,
    TaskId
)
from .download import DownloadTask


class StopTask:
    def __init__(self):
        self.priority = -float("inf")
    def __lt__(self, other):
        return self.priority < other.priority

class Downloader:
    download_tasks: dict[TaskId, DownloadTask] = {}
    running_tasks:   dict[TaskId, asyncio.Task] = {}
    _looper_task = None
    
    def __init__(
        self,
        prop: DownloadProperties = None,
        loop: asyncio.AbstractEventLoop = None,
    ):
        self._loop = loop
        self.prop = prop or DownloadProperties()
        self.tasks_queue: asyncio.PriorityQueue[DownloadTask] = asyncio.PriorityQueue()
        self.semaphore = asyncio.Semaphore(self.prop.max_tasks_concurrent)
        self.is_running = False
        self.stop_event = asyncio.Event()
        self._looper_task: Optional[asyncio.Task] = None
        self._background_tasks: list[asyncio.Task] = []
        self._done_waiters: list[DownloadWaiter] = []
        self._put_waiters: list[DownloadWaiter] = []
        self._done_waiters_map: dict[TaskId, asyncio.Future] = {}
        self._put_waiters_map: dict[TaskId, asyncio.Future] = {}
        # self._lock = asyncio.Lock()
        self._is_set_signal = False
    
    def set_signal_stop(self):
        '''
        Set signal handler for SIGINT to stop the downloader, used for force stop.
        You can call this method after creating the downloader object.
        Function stop() will be called when you press Ctrl+C.
        '''
        def wrapper(sig, frame):
            logger.info("Force stopping the downloader...")
            self._loop.create_task(self.stop())

        signal.signal(signal.SIGINT, wrapper)
        self._is_set_signal = True

    def set_signal_cancel(self):
        '''
        Set signal handler for SIGINT to stop the downloader, used for graceful shutdown.
        You can call this method after creating the downloader object.
        Function cancel() will be called when you press Ctrl+C.
        '''
        def wrapper(sig, frame):
            logger.info("Canceling running tasks. Gracefully stopping the downloader... ")
            self._loop.create_task(self.cancel())
        
        signal.signal(signal.SIGINT, wrapper)
        self._is_set_signal = True
    
    def remove_signal(self):
        '''
        Remove signal handler for SIGINT.
        Set signal handler to default behavior.
        '''
        if self._is_set_signal:
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            self._is_set_signal = False
    
    def start(self):
        if self.is_running:
            return
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        self.stop_event.clear()
        self._looper_task = self._loop.create_task(self.looper())
        self.is_running = True
        return self._looper_task
    
    async def stop(self):
        await self._stop()
        await self.wait_forever()
        self.clear_waiters()
        self.is_running = False
    
    async def _stop(self):
        self.stop_event.set()
        self.tasks_queue.put_nowait(StopTask())
        if self._is_set_signal:
            self.remove_signal()
    
    async def cancel(self):
        await self._stop()
        for task_id in self.running_tasks.keys():
            download_task = self.download_tasks.get(task_id)
            await download_task.controller.cancel()
        await self.wait_forever()
        self.clear_waiters()
        self.is_running = False

    def create_task(
        self,
        url: str,
        save_path: str,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None,
        file_sha256: Optional[str] = None,
        background_result: bool = True,
        start: bool = True,
        priority: int = 0,
        json: Optional[Union[dict, list]] = None,
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
        task = DownloadTask(info, self.prop, start=start, priority=priority, background_result=background_result)
        self._put_download_task(task)
        return task.task_id
    
    async def looper(self):
        def done_callback(download_task: DownloadTask):
            def inner(task: asyncio.Task[Union[DownloadResult, None]]):
                result = None
                try:
                    result = task.result()
                    if download_task._wait_complete:
                        self._background_tasks.append(self._loop.create_task(download_task.scheduler.complete()))
                except asyncio.CancelledError:
                    logger.error(f"Task {download_task.task_id} {download_task.info.file_name} Cancelled")
                    self.prop.progress_tracker.on_cancel(download_task.task_id)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Task {download_task.task_id} {download_task.info.file_name} download failed: {e}")
                    self.prop.progress_tracker.on_error(download_task.task_id, e)
                else:
                    self.prop.progress_tracker.on_complete(download_task.task_id, result)
                finally:
                    self._clean_task(download_task.task_id, result)
            return inner
        
        while not self.stop_event.is_set():
            try:
                if len(self.running_tasks) >= self.prop.max_tasks_concurrent:
                    continue
                
                download_task = await self.tasks_queue.get()
                if isinstance(download_task, StopTask):
                    break
                
                task = download_task.start(self.semaphore)
                task.add_done_callback(done_callback(download_task))
                self._put_task(download_task.task_id, task)
            finally:
                await asyncio.sleep(1)
    
    def _clean_task(self, task_id: TaskId, result: Optional[DownloadResult]):
        try:
            if result is None:
                logger.info(f"Task {task_id} download failed")
            elif result.success:
                download_task: DownloadTask = self.download_tasks[task_id]
                if not download_task._wait_complete:
                    logger.info(f"Task {task_id} {download_task.info.file_name} download success")
            else:
                logger.info(f"Task {task_id} download failed {result}")
        finally:
            self.prop.progress_tracker.advance_main()
            self.running_tasks.pop(task_id, None)
            self._wakeup_waiter(self._done_waiters_map, task_id)
            self._wakeup_waiter(self._done_waiters)
    
    def _put_download_task(self, task: DownloadTask):
        self.download_tasks[task.task_id] = task
        self.tasks_queue.put_nowait(task)
    
    def _put_task(self, task_id: TaskId, task: asyncio.Task):
        self.running_tasks[task_id] = task
        self._wakeup_waiter(self._put_waiters_map, task_id)
        self._wakeup_waiter(self._put_waiters)
    
    async def cancel_task_current(self, task_id: TaskId, accept_wait: bool = False):
        '''
        Cancel a task by task_id. This method will call Task().cancel() to cancel the task.
        If accept_wait is True, it will wait for the task to be put into the queue and then cancel it.
        If background is True, it will create a task to cancel the task in the background if it's not running yet.
        '''
        if download_task := self.download_tasks.get(task_id):
            if download_task._task.done():
                return
            if download_task._task is None:
                if not accept_wait:
                    return
                await self.wait_task_start(task_id)
            download_task._task.cancel()
    
    async def cancel_task(self, task_id: TaskId, accept_wait: bool = False):
        '''
        Cancel a task by task_id. This method will call DownloadTask().controller.cancel() to cancel the task.
        If accept_wait is True, it will wait for the task to be put into the queue and then cancel it.
        If background is True, it will create a task to cancel the task in the background if it's not running yet.
        '''
        if download_task := self.download_tasks.get(task_id):
            if download_task._task.done():
                return
            if download_task._task is None:
                if not accept_wait:
                    return
                await self.wait_task_start(task_id)
            await download_task.controller.cancel()
    
    def _wakeup_waiter(self, waiters: Union[list[DownloadWaiter], dict[TaskId, asyncio.Future]], task_id: TaskId = None):
        if isinstance(waiters, dict):
            waiter = waiters.pop(task_id, None)
            if waiter and not waiter.done():
                waiter.set_result(None)
        elif isinstance(waiters, list):
            for i in range(len(waiters)-1, -1, -1):
                waiter = waiters[i]
                waiter.count -= 1
                if waiter.count <= 0:
                    waiters.pop(i)
                    if not waiter.waiter.done():
                        waiter.waiter.set_result(None)
    
    async def wait_background_tasks(self):
        '''
        Attentions: This method will wait for now running background tasks to complete.
        '''
        if self._background_tasks:
            tasks = self._background_tasks.copy()
            self._background_tasks.clear()
            await asyncio.wait(tasks)
    
    async def wait_forever(self):
        '''Wait for looper run forever until stop event is set or signal is received.'''
        await self.stop_event.wait()
        await self._wait_running_tasks_done()
        await self.wait_background_tasks()
    
    async def _wait_running_tasks_done(self, timeout: Optional[float] = None):
        '''
        Wait for now running tasks to complete.
        '''
        if self.running_tasks:
            await asyncio.wait(self.running_tasks.values(), timeout=timeout)
    
    async def wait_task(self, task_id: TaskId, timeout: Optional[float] = None):
        download_task = self.download_tasks.get(task_id)
        if download_task is None:
            raise ValueError(f"Task {task_id} not found")
        if download_task._task is None:
            await self.wait_task_start(task_id, timeout=timeout)
    
    async def wait_task_start(self, task_id: TaskId, timeout: Optional[float] = None):
        waiter = self._register_waiter_map(self._put_waiters_map, task_id)
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
    
    async def wait_any_tasks_done(self, count: int = 1, timeout: Optional[float] = None):
        if count <= 0:
            return
        waiter = self._register_waiter_list(self._done_waiters, count)
        try:
            await asyncio.wait_for(waiter, timeout=timeout)
        except:
            waiter.cancel()
            try:
                self._done_waiters.remove(waiter)
            except:
                pass
            raise
    
    def _register_waiter_map(self, waiter_map: dict[TaskId, asyncio.Future], task_id: TaskId):
            if task_id not in waiter_map:
                waiter_map[task_id] = self._loop.create_future()
            return waiter_map[task_id]
    
    def _register_waiter_list(self, waiter_list: list[DownloadWaiter], count: int = 1):
        for w in filter(lambda waiter: waiter.count == count, waiter_list):
            return w.waiter
        waiter = self._loop.create_future()
        waiter_list.append(DownloadWaiter(waiter, count))
        return waiter
    
    def clear_waiters(self):
        def set_result(waiter: asyncio.Future):
            if not waiter.done():
                waiter.set_result(None)
        for waiter in self._done_waiters:
            set_result(waiter.waiter)
        for waiter in self._put_waiters:
            set_result(waiter.waiter)
        for waiter in self._done_waiters_map.values():
            set_result(waiter)
        for waiter in self._put_waiters_map.values():
            set_result(waiter)
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
    
    def __del__(self):
        if self._is_set_signal:
            self.remove_signal()
        if not all([task.done() for task in self._background_tasks]):
            logger.warning(f"Background tasks has not been completed, use wait_background_tasks() to wait for them to complete")