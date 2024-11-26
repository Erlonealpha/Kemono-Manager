import os
import asyncio
from aiohttp import (
    ClientError,
        ClientPayloadError, 
        ClientResponseError, 
            ClientHttpProxyError,
        ClientConnectionError, 
            # ClientOSError,
            #     ClientConnectorError,
                    ClientProxyConnectionError,
                    ClientSSLError,
                        # ClientConnectorSSLError,
                        # ClientConnectorCertificateError
)
from aiofiles import open as aio_open
from pathlib import Path
from time import time as now_time
from typing import Optional, Awaitable

from kemonobakend.utils import async_verify_file_sha256, path_join, IdGenerator
from kemonobakend.log import logger
from .types import (
    DownloadInfo, DownloadResult, DownloadProperties, DownloadStatus,
    get_ranges, TaskId
)


class DownloadController:
    def __init__(self, task: 'DownloadTask'):
        self.task = task
        self.lock = asyncio.Lock()
        self.condition = asyncio.Condition()
    
    async def cancel(self):
        async with self.lock:
            self.task.status.set_status(DownloadStatus.CANCELLED)
            if self.task.status.is_paused:
                await self.condition.notify_all()
            raise NotImplementedError("Cancel download not implemented")  # cancel download
    
    async def retry(self):
        pass
    
    async def start(self):
        async with self.lock:
            if self.task.status.is_downloading:
                return
            if self.task.status.is_cancelled:
                return await self._handle_cancel()
            self.task.status.set_status(DownloadStatus.DOWNLOADING)
    
    async def pause(self):
        async with self.lock:
            if self.task.status.is_paused:
                return
            if self.task.status.is_cancelled:
                return await self._handle_cancel()
            self.task.status.set_status(DownloadStatus.PAUSED)
    
    async def resume(self):
        async with self.lock:
            if not self.task.status.is_paused:
                return
            if self.task.status.is_cancelled:
                return await self._handle_cancel()
            self.task.status.set_status(DownloadStatus.RESUMED)
            await self.condition.notify_all()
            self.task.status.set_status(DownloadStatus.DOWNLOADING)
    
    async def complete(self):
        async with self.lock:
            self.task.status.set_status(DownloadStatus.COMPLETED)
    
    async def handle_pause(self):
        async with self.lock:
            if self.task.status.is_paused:
                await self._handle_pause()
                return True
    
    async def _handle_pause(self):
        await self.condition.wait()
        if self.task.status.is_cancelled:
            return await self._handle_cancel()
        raise NotImplementedError("Handle pause not implemented")  # resume download
    
    async def handle_cancel(self):
        async with self.lock:
            if self.task.status.is_cancelled:
                await self._handle_cancel()
                return True
    
    async def _handle_cancel(self):
        self.task.status.set_status(DownloadStatus.CANCELLED)
        raise NotImplementedError("Handle cancel not implemented")  # cancel download

class DownloadSchedulerTask:
    def __init__(self, scheduler: 'DownloadScheduler', range):
        self.scheduler = scheduler
        self.download_task = scheduler.task
        
        self.start_pos = range[0]
        self.end_pos = range[1]
        self.range_str = f"{self.start_pos}-{self.end_pos}"
        self.range_size = self.end_pos - self.start_pos + 1
        self.chunk_size = 1024 * 256
        self.handle_size = 1024 * 512
        self.now_size = 0
        self.mode: str = "wb"
        self.chunk_path = Path(path_join(self.download_task.prop.tmp_path, f'{self.download_task.info.file_name}_{self.range_str}.part'))
        self.last_speed_check = None
        self.speed_check_interval = 10
    
    def update_progress(self, size):
        self.download_task.prop.progress_tracker.advance(self.download_task.task_id, size)
    
    def pre_start(self):
        if not self.chunk_path.parent.exists():
            self.chunk_path.parent.mkdir(parents=True)
        if self.chunk_path.exists():
            self.mode = 'r+b'
            file_size = self.chunk_path.stat().st_size
            if file_size == self.range_size:
                logger.debug(f"File: {self.download_task.info.file_name} chunk {self.range_str} already exists, skipping download")
                return False
            elif file_size > self.range_size:
                logger.error(f"File: {self.download_task.info.file_name} chunk {self.range_str} already exists with size {file_size}, but expected size is {self.range_size}")
                self.chunk_path.unlink()
            elif file_size != self.now_size:
                self.now_size = file_size
                self.update_progress(file_size)
                logger.debug(f"File: {self.download_task.info.file_name} chunk {self.range_str} already exists with size {file_size}, but expected size is {self.range_size}")
        else:
            self.mode = 'wb'
        return True

    async def download(self, retries=3):
        self.scheduler.running_count += 1
        try:
            while retries > 0:
                ret = await self._download()
                if ret == "resume" or ret == "speed_check":
                    continue
                elif ret == "cancel":
                    return False
                elif ret is True:
                    return True
                retries -= 1
            return False
        finally:
            self.scheduler.running_count -= 1
            self.scheduler.wait_count -= 1
    
    async def _download(self):
        def todo(size):
            nonlocal counter
            counter += size
            if counter >= self.handle_size or size < self.chunk_size:
                return True, 
            return False
        if not self.pre_start():
            self.update_progress(self.range_size)
            return True
        async with self.download_task.prop.session_pool.get() as session:
            await self.download_task.controller.start()
            range_start = self.start_pos + self.now_size
            try:
                async with session.get(self.download_task.info.url, headers={'Range': f'bytes={range_start}-{self.end_pos}'}) as response:
                    if response.status == 206:
                        async with aio_open(self.chunk_path, self.mode) as f:
                            await f.seek(self.now_size)
                            counter = 0
                            async for chunk in response.content.iter_chunked(self.chunk_size):
                                chunk_size = len(chunk)
                                await f.write(chunk)
                                self.now_size += chunk_size
                                self.download_task.result.downloaded_size += chunk_size
                                self.update_progress(chunk_size)
                                if self.speed_check():
                                    return "speed_check"
                                if todo(chunk_size):
                                    if await self.download_task.controller.handle_pause():
                                        return "resume"
                                    if await self.download_task.controller.handle_cancel():
                                        return "cancel"
                                    counter = 0
                            return True
                    elif response.status == 200:
                        logger.warning(f"Download of file: {self.download_task.info.file_name} may have no range support")
                        return False
                    elif response.status == 416:
                        logger.warning(f"Download of file: {self.download_task.info.file_name} range {self.start_pos}-{self.end_pos} is out of bounds")
                        return False
                    elif response.status == 429:
                        logger.warning(f"Download of file: {self.download_task.info.file_name} rate limit exceeded")
                        await asyncio.sleep(2)
                    else:
                        logger.error(f"Download of file: {self.download_task.info.file_name} failed with status code {response.status}")
                        return False
            except ClientProxyConnectionError as e:
                logger.error(f"{e}")
            except ClientSSLError as e:
                logger.error(f"{e}")
            except ClientConnectionError as e:
                logger.error(f"{e}")
            except ClientHttpProxyError as e:
                logger.error(f"{e}")
            except ClientPayloadError as e:
                logger.error(f"{e}")
            except ClientResponseError as e:
                logger.error(f"{e}")
            except KeyboardInterrupt:
                logger.error("KeyboardInterrupt")
                self.download_task.status.set_status(DownloadStatus.CANCELLED)
                return "cancel"
            except Exception as e:
                logger.error(f"{e}")
    
    def speed_check(self) -> bool:
        try:
            if self.scheduler.wait_count <= 3 and \
                self.download_task.prop.progress_tracker.get_speed(self.download_task.task_id) < 1024*1024 and \
                (self.last_speed_check is None or (self.last_speed_check is not None and  now_time() - self.last_speed_check > self.speed_check_interval)):
                self.last_speed_check = now_time()
                return True
        except:
            pass
        return False

class DownloadScheduler:
    def __init__(self, task: 'DownloadTask'):
        self.task = task
        ranges = get_ranges(self.task.info.file_size, chunk_size=self.task.chunk_size, chunks=self.task.num_chunks)
        self.running_count = 0
        self.wait_count = len(ranges)
        self.tasks = [
            DownloadSchedulerTask(self, range)
            for range in ranges
        ]
        self.failed_tasks = []
        self.semaphore = asyncio.Semaphore(self.task.prop.per_task_max_concurrent)
    
    async def merge_files(self):
        async def merge_file(task: DownloadSchedulerTask):
            async with aio_open(task.chunk_path, 'rb+') as f:
                async with aio_open(self.task.info.save_path, 'rb+') as out_f:
                    await out_f.seek(task.start_pos)
                    await out_f.write(await f.read())
        p = Path(self.task.info.save_path)
        if not p.parent.exists():
            p.parent.mkdir(parents=True)
        async with aio_open(self.task.info.save_path, 'wb'):
            pass
        await asyncio.gather(*[self.semaphore_limited_task(merge_file(task), asyncio.Semaphore(24)) for task in self.tasks])
    
    def remove_tmp_files(self):
        for task in self.tasks:
            task.chunk_path.unlink()
    
    async def start_download(self):
        tasks = await asyncio.gather(*[self.semaphore_limited_task(task.download(), self.semaphore) for task in self.tasks])
        if not all(tasks):
            self.failed_tasks = [task for task, success in zip(self.tasks, tasks) if not success]
            self.task.status.set_status(DownloadStatus.FAILED)
            self.task.result.message = "有部分分片下载失败"
            return False
        await self.merge_files()
        if self.task.info.file_sha256 is not None:
            if self.task.prop.file_strict and not await async_verify_file_sha256(self.task.info.save_path, self.task.info.file_sha256):
                logger.error(f"File: {self.task.info.file_name} sha256 verification failed")
                self.task.status.set_status(DownloadStatus.FAILED)
                self.task.result.message = "文件校验失败"
                os.remove(self.task.info.save_path)
                return False
            elif self.task.prop.file_strict:
                self.remove_tmp_files()
                logger.info(f"File: {self.task.info.file_name} sha256 verified")
                
        elif self.task.prop.file_strict:
            logger.warning(f"File: {self.task.info.file_name} sha256 verification not provided, skipping")
        else:
            self.remove_tmp_files()
        
        self.task.status.set_status(DownloadStatus.COMPLETED)
        return True
    
    async def semaphore_limited_task(self, task: Awaitable[bool], semaphore: asyncio.Semaphore):
        async with semaphore:
            return await task

class DownloadTask:
    def __init__(
        self, 
        info: DownloadInfo,
        prop: DownloadProperties,
        priority: int,
        start: bool = True,
        num_chunks: Optional[int] = None,
        chunk_size: Optional[int] = None,
    ):
        self.task_id: TaskId = IdGenerator.generate(self.__class__.__name__)
        self.info = info
        self.prop = prop
        self.priority = priority
        self._start = start
        self.num_chunks = num_chunks
        self.chunk_size = chunk_size
        self.status = DownloadStatus()
        self.controller = DownloadController(self)
        self.scheduler = None
        self.result = DownloadResult()

    def pre_start(self):
        self.prop.progress_tracker.add_task(self.task_id, "下载", self.info.file_name, self.info.file_size)
    
    async def start(self):
        if await async_verify_file_sha256(self.info.save_path, self.info.file_sha256, strict=True):
            logger.info(f"File: {self.info.file_name} already exists and sha256 verified, skipping download")
            return True
        
        if self.info.file_size is None:
            self.info.file_size = await self.info.get_file_size(session_pool=self.prop.session_pool)
            if self.info.file_size is None:
                raise ValueError(f"Failed to get file size of {self.info.file_name}")
        
        self.scheduler = DownloadScheduler(self)
        self.pre_start()
        
        ret = await self.scheduler.start_download()
        self.prop.progress_tracker.remove_task(self.task_id)
        return ret
    
    def dump(self):
        '''
        ```json
        {
            "task_id": ...,
            "info": {
                "url": ...,
                "file_name": ...,
                "file_size": ...,
                "file_sha256": ...,
                "save_path": ...,
                ...
            },
            "priority": ...,
            "num_chunks": ...,
            "chunk_size": ...,
            "status": {
                "status": ...,
                "message": ...,
                ...
            },
        }
        ```
        '''
        return {
            'task_id': self.task_id,
            'info': self.info.dump(),
            'priority': self.priority,
            'num_chunks': self.num_chunks,
            'chunk_size': self.chunk_size,
            'status': self.status.dump(),
        }
    
    def __lt__(self, other: 'DownloadTask'):
        return self.priority < other.priority
