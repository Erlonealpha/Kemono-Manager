import asyncio
from aiohttp import  ClientTimeout
from dataclasses import dataclass

from typing import Optional, Union, NewType, Generic, TypeVar, Any

from kemonobakend.session_pool import SessionPool
from kemonobakend.utils import get_num_and_unit, to_bytes
from kemonobakend.utils.progress import DownloadProgress, ProgressTask
from kemonobakend.config import settings
from kemonobakend.log import logger

TaskId = NewType('TaskId', int)

class DownloadError(Exception):
    pass

T = TypeVar('T')

class TaskMap(dict):
    pass

@dataclass
class DownloadWaiter:
    waiter: asyncio.Future
    count: int = 1
    def __eq__(self, other: Union[int, 'DownloadWaiter']):
        if isinstance(other, DownloadWaiter):
            other = other.count
        return self.count == other

class NoneValue:
        pass
class AutoList(Generic[T]):
    def __init__(self, items: Optional[list[T]] = None):
        if items is None:
            items = []
        self.items = items
        self._items_cache = None
    
    def append(self, value):
        self.items.append(value)
        self._cache_append(value)
    
    def extend(self, values):
        self.items.extend(values)
        self._cache_extend(values)
    
    def remove(self, value):
        i = self.items.index(value)
        self.items[i] = NoneValue
        self._reset_cache()
    
    def pop(self, index: int = -1):
        r = self.items[index]
        self.items[index] = NoneValue
        self._reset_cache()
        return r
    
    def clear(self):
        self.items = []
    
    def _reset_cache(self):
        self._items_cache = None
    
    def _cache_append(self, value):
        if self._items_cache is None:
            self._items_cache = []
        self._items_cache.append(value)
    
    def _cache_extend(self, values):
        if self._items_cache is None:
            self._items_cache = []
        self._items_cache.extend(values)
    
    @property
    def _items(self):
        if self._items_cache is None:
            self._items_cache = [i for i in self.items if i is not NoneValue]
        return self._items_cache
    
    def _set_to(self, index, value):
        vals = [None] * (index - len(self.items) + 1)
        self.items.extend(vals)
        self._cache_extend(vals)
        if value is not None:
            self.items[index] = value
            self._items_cache[-1] = value
    
    def __iter__(self):
        return iter(self._items)
    
    def __getitem__(self, index):
        try:
            e = self.items[index]
            if e is NoneValue:
                raise IndexError()
            return e
        except IndexError:
            self._set_to(index)
            return None
    
    def __setitem__(self, index, value):
        try:
            self._reset_cache()
            self.items[index] = value
        except IndexError:
            self._set_to(index, value)
    
    def __len__(self):
        return len(self._items)
    
    def __bool__(self):
        return bool(self.items)
    
    def __str__(self):
        return str(self.items)
    
    def __repr__(self):
        return f"AutoList({self.items.__repr__()})"

@dataclass
class DownloadInfo:
    url: str
    file_name: str
    save_path: str
    file_sha256: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    headers: Optional[dict] = None
    cookies: Optional[dict] = None
    json: Optional[Union[dict, list]] = None
    
    async def get_file_size(self, session_pool: SessionPool, retry = 3) -> Optional[int]:
        while retry > 0:
            try:
                async with session_pool.get() as session:
                    async with session.head(self.url, allow_redirects=True, headers=self.headers, cookies=self.cookies) as response:
                        if response.status in [200, 201, 206]:
                            return response.content_length
                        elif response.status == 429:
                            retry -= 0.5
                            await asyncio.sleep(1)
                        elif response.status == 404:
                            logger.warning(f"File not found: {self.url}")
                            return None
            except Exception as e:
                logger.error(f"({retry})Error getting file size {self.url}: {e}")
                retry -= 1
        return None

    def dump(self):
        return {
            "url": self.url,
            "file_name": self.file_name,
            "save_path": self.save_path,
            "file_sha256": self.file_sha256,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "headers": self.headers,
            "cookies": self.cookies,
            "json": self.json,
        }

class ProgressTracker:
    def __init__(self, progress: DownloadProgress = None):
        self.progress = progress or DownloadProgress()
        self.task_id_map: dict[int, ProgressTask] = {}
    
    def _get_p_task(self, task_id: TaskId):
        p_task = self.task_id_map.get(task_id)
        if p_task is None:
            raise ValueError(f"Download Task id {task_id} not found in progress tracker")
        return p_task
    
    def add_main_task(self, description: str, total: int):
        return self.add_task(-1, description, None, total)

    def remove_main_task(self):
        self.remove_task(-1)
    
    def advance_main(self, downloaded_size: int=1):
        if -1 not in self.task_id_map:
            return
        self.advance(-1, downloaded_size)
    
    def add_task(self, task_id: TaskId, description: str, file_name: str, total_size: int):
        p_task = self.progress.add_task(description, file_name, total=total_size)
        self.task_id_map[task_id] = p_task
        return p_task
    
    def remove_task(self, task_id: TaskId):
        p_task = self._get_p_task(task_id)
        p_task.remove()
        self.task_id_map.pop(task_id)
    
    def advance(self, task_id: TaskId, downloaded_size: int):
        p_task = self._get_p_task(task_id)
        p_task.advance(downloaded_size)
    
    def get_speed(self, task_id: TaskId):
        p_task = self._get_p_task(task_id)
        return p_task.get_speed()

    def on_complete(self, task_id: TaskId, result: 'DownloadResult'):
        pass
    
    def on_error(self, task_id: TaskId, error: Exception):
        pass
    
    def on_cancel(self, task_id: TaskId):
        pass

class DownloadProperties:
    def __init__(
        self, 
        session_pool: SessionPool = None,
        progress_tracker: ProgressTracker = None,
        progress: DownloadProgress = None,
        tmp_path: str = settings.download.tmp_path,
        max_tasks_concurrent: int = 8,
        per_task_max_concurrent: int = 16,
        max_retries: int = 2,
        timeout: ClientTimeout = ClientTimeout(**settings.download.timeout_kwargs),
        file_strict: bool = True,
    ):
        self.tmp_path = tmp_path
        self.session_pool = session_pool or SessionPool(enabled_accounts_pool=True)
        self.progress_tracker = progress_tracker or ProgressTracker(progress)
        self.max_tasks_concurrent = max_tasks_concurrent
        self.per_task_max_concurrent = per_task_max_concurrent
        self.max_retries = max_retries
        self.timeout = timeout
        self.file_strict = file_strict

class DownloadResult:
    def __init__(self, success: bool = False, message: str = "Pending", *, total_size = None, task_id: TaskId = None):
        self.success = success
        self._message = message
        self.message_history = []
        self.downloaded_size = 0
        self.total_size = total_size
        self.task_id = task_id
    
    @property
    def message(self) -> str:
        return self._message
    @message.setter
    def message(self, value: str):
        self._message = value
        self.message_history.append(value)
    
    def __str__(self):
        return f"DownloadResult(success={self.success}, message={self.message}, downloaded_size={self.downloaded_size}, total_size={self.total_size}, task_id={self.task_id})"
    
    def __repr__(self):
        return self.__str__()

class Status:
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RESUMED = "resumed"
class DownloadStatus(Status):
    status: str = "pending"
    
    is_pending: bool = True
    is_downloading: bool = False
    is_completed: bool = False
    is_failed: bool = False
    is_cancelled: bool = False
    
    is_paused: bool = False
    is_resumed: bool = False

    _prev_status: str = "pending"

    def __init__(self, status: str = "pending"):
        if status != "pending":
            self.set_status(status)
    
    def set_status(self, status: str):
        assert status in ["pending", "downloading", "completed", "failed", "cancelled", "paused", "resumed"], "Invalid status"
        setattr(self, f"is_{status}", True)
        setattr(self, f"is_{self._prev_status}", False)
        self._prev_status = self.status
        self.status = status
    
    def dump(self):
        return {
            "status": self.status,
            "is_pending": self.is_pending,
            "is_downloading": self.is_downloading,
            "is_completed": self.is_completed,
            "is_failed": self.is_failed,
            "is_cancelled": self.is_cancelled,
            "is_paused": self.is_paused,
            "is_resumed": self.is_resumed,
        }

def parse_splits(target_size, dic: dict[str, int] = None) -> list[tuple[int, int]]:
    if dic is None:
        dic = settings.download.auto_chunks_dict
    try:
        for k, v in dic.items():
            s_pos, e_pos = k.split("-") 
            if s_pos == "": 
                s_pos = 0
            if s_pos[-1] != "B":
                e_pos, unit = get_num_and_unit(e_pos)
                s_pos = to_bytes(s_pos, unit)
                e_pos = to_bytes(e_pos, unit) if e_pos != "" else None
            else:
                s_pos = to_bytes(s_pos)
                e_pos = to_bytes(e_pos) if e_pos != "" else None
            if e_pos is not None:
                if s_pos < target_size <= e_pos:
                    return v
            else:
                return v
    except Exception as e:
        logger.warning(f"Error in parse_splits: {e}")
        return 1

def get_ranges(size, *, chunk_size=None, chunks=None, auto_chunks_dict=None):
    if chunk_size is not None:
        chunks = size // chunk_size
    elif chunks is None:
        chunks = parse_splits(size, auto_chunks_dict)
    return [(i*size//chunks, min((i+1)*size//chunks-1, size)) for i in range(chunks)]

