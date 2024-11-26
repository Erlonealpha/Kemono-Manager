if __name__ == '__main__':
    from os import getcwd
    from sys import path
    path.append(getcwd())

from aiohttp import (
    ClientSession as _ClientSession, TCPConnector, ClientTimeout, UnixConnector, 
    NamedPipeConnector, TraceConfig, TraceRequestExceptionParams,
    TraceRequestEndParams)

import asyncio
from heapq import heapify, heappush, heappop
from concurrent.futures import Future
from collections import deque

from random import choice

from kemonobakend.proxy import (
    Proxies, Proxy, 
    BaseSaveLoad, ProxiesSaveLoad, ProxiesInfoSaveLoad, SaveLoadManager
)
from kemonobakend.accounts_pool import AccountsPool, Account
from kemonobakend.utils import UA_RAND
from kemonobakend.utils.helpers import get_running_loop
from kemonobakend.config import settings

from typing import Callable, Generator, Optional, Type, TypeVar, Union, Any, List

INT64MAX = 2**31-1

class ProxiesSaveLoadSP(ProxiesSaveLoad):
    save_path = 'data/session_pool/proxies.json'
class SessionPoolSaveLoad(BaseSaveLoad):
    save_path = 'data/session_pool/config.json'


class ClientSession(_ClientSession):
    def __init__(self, id: int, proxy: Optional[Proxy]=None, *args, **kwargs):
        self._prepared = False
        self.id = id
        self.proxy = proxy
        self.max_use = None
        self.is_valid = True
        self.used_count = 0
        self._args = args
        self._kwargs = kwargs
        self.kemono_account: Optional[Account] = None
        self._is_set_kemono_cookies: bool = False
        self._set_cookies_failed_count = 0
        self._wait_for_set_cookies = None

    def init(self, *args, **kwargs):
        if not args: args = self._args 
        if not kwargs: kwargs = self._kwargs
        super().__init__(*args, **kwargs)
        self._prepared = True
    
    async def _request(self, *args, **kwargs):
        if self.proxy is not None and not kwargs.get("proxy"):
            kwargs['proxy'] = self.proxy.url
        if self.kemono_account is not None and not self._is_set_kemono_cookies:
            skip = False
            if self._set_cookies_failed_count >= 2:
                # 5 minutes later, try next time
                self._wait_for_set_cookies = asyncio.get_running_loop().time() + (60*5)
                self._set_cookies_failed_count = 0
                skip = True
            elif self._wait_for_set_cookies is not None and asyncio.get_running_loop().time() >= self._wait_for_set_cookies:
                self._wait_for_set_cookies = None
            else:
                skip = True
            if not skip:
                cookies = await self.kemono_account.get_cookies(self.proxy.url)
                if not cookies:
                    ret = await self.kemono_account.try_register(self.proxy.url)
                    if ret:
                        cookies = self.kemono_account.cookies
                        self._is_set_kemono_cookies = True
                    else:
                        self._set_cookies_failed_count += 1
                else:
                    self._is_set_kemono_cookies = True
            else:
                cookies = None
        else:
            cookies = None
        if (cookies_ := kwargs.pop('cookies', None)) is not None:
            pass
        return await super()._request(*args, cookies=cookies, **kwargs)

    def __init_subclass__(cls: _ClientSession) -> None:
        # ignore warning
        pass
    
    def __lt__(self, other: 'ClientSession') -> bool:
        return self.proxy.__lt__(other.proxy)
    
    def __gt__(self, other: 'ClientSession') -> bool:
        return self.proxy.__gt__(other.proxy)
    
    def __eq__(self, value: 'ClientSession') -> bool:
        return self.id == value.id

class QueueEmptyError(Exception):
    pass

class QueueFullError(Exception):
    pass

T = TypeVar('T')
class AbstractHandler:
    def empty(self) -> bool: ...
    def full(self) -> bool: ...
    def put(self, item: T) -> None: ...
    def get(self) -> Optional[T]: ...

class AsyncSessionPoolQueue:
    def __init__(self, handler: Type[AbstractHandler], loop: asyncio.AbstractEventLoop):
        self.handler = handler

        self._loop = loop
        self._getters: deque[Future[Any]] = deque()
        self._putters: deque[Future[Any]] = deque()
        # self._finished = Event()
    
    def empty(self) -> bool:
        return self.handler.empty()
    
    def full(self) -> bool:
        return self.handler.full()
    
    def _wakeup_next(self, waiters: deque[Future[Any]]) -> None:
        while waiters:
            waiter = waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)
                break
    
    async def put(self, item: T) -> None:
        while self.full():
            putter = self._loop.create_future()
            self._putters.append(putter)
            try:
                await putter
            except:
                putter.cancel()
                try:
                    self._putters.remove(putter)
                except ValueError:
                    pass
                if not self.full() and not putter.cancelled():
                    self._wakeup_next(self._putters)
                raise
        self.put_nowait(item)
    
    def put_nowait(self, item: T) -> None:
        if self.full():
            raise QueueFullError('SessionPool queue is full')
        self._put(item)
        self._wakeup_next(self._getters)
    
    def _put(self, item: T) -> None:
        self.handler.put(item)
    
    async def get(self, **get_kwargs) -> T:
        while self.empty():
            getter = self._loop.create_future()
            self._getters.append(getter)
            try:
                await getter
            except:
                getter.cancel()
                try:
                    self._getters.remove(getter)
                except ValueError:
                    pass
                if not self.empty() and not getter.cancelled():
                    self._wakeup_next(self._getters)
                raise
        return self.get_nowait(**get_kwargs)
    
    def get_nowait(self, **get_kwargs) -> T:
        if self.empty():
            raise QueueEmptyError('SessionPool queue is empty')
        item = self._get(**get_kwargs)
        self._wakeup_next(self._putters)
        return item

    def _get(self, **get_kwargs) -> T:
        return self.handler.get(**get_kwargs)

class PoolHandlerError(Exception):
    '''pool handler error'''

class PoolHandler(AbstractHandler):
    def __init__(self, session_pool: 'SessionPool', max_try_get = 16):
        self.session_pool = session_pool
        self.max_use_per = self.session_pool.per_session_max_use \
            if self.session_pool.per_session_max_connections == 'auto' else self.session_pool.per_session_max_connections
        # self._cache_sessions: Optional[list[ClientSession]] = None
        self.max_try_get = max_try_get
        self._max_conn_ids = set()
        self._get_count = 0
        self._lock = asyncio.Lock()
        self._el = 0
        self.init()
    
    def init(self):
        self._full_size = len(self.session_pool.sessions_raw) * self.max_use_per
    
    def full(self):
        # no wait
        return False
    def empty(self):
        return self._get_count >= self._full_size
    
    def pop_random_session(self, sessions: list[ClientSession]) -> Optional[ClientSession]:
        if len(sessions) == 1:
            return sessions[0]
        index = None
        for i in range(len(sessions) - 1):
            try:
                first = sessions[i]
                second = sessions[i+1]
                if self.session_pool.priority_type.sequence_positive():
                    elp = (first.proxy.priority - second.proxy.priority) / first.proxy.priority
                else:
                    elp = (second.proxy.priority - first.proxy.priority) / second.proxy.priority
            except ZeroDivisionError:
                elp = 0
            # 根据差值百分比和设定的阈值，判断是否需要随机选择，避免短时间内过多重复选择
            if any((first.proxy.force_priority is not None, second.proxy.force_priority is not None)) \
                and 0.98 > elp > settings.session_pool.elp_threshold:
                # 0.98 用于当设置了数值很大的force_priority时 
                index = i+1
                break
            elif elp > settings.session_pool.elp_threshold:
                index = i+1
                break
                
        if index is not None:
            sessions_ = sessions[:index]
        else:
            sessions_ = sessions
        one = choice(sessions_)
        sessions.remove(one)
        return one
    
    def get(self, **get_kwargs) -> Optional[ClientSession]:
        try_get = 0
        while self.max_try_get is None or try_get < self.max_try_get:
            try_get += 1
            if len(self.session_pool.sessions_heap) == 0 and len(self._max_conn_ids) == 0:
                raise QueueEmptyError('SessionPool queue has not available sessions')
            
            original_priority_type = None
            if (priority_type := get_kwargs.get('priority_type')) is not None:
                original_priority_type = self.session_pool.priority_type.get_type()
                self.session_pool.priority_type.set_type(priority_type)
            sessions = [    
                heappop(self.session_pool.sessions_heap)
                for _ in range(min(12, len(self.session_pool.sessions_heap)))
            ]
            if original_priority_type is not None:
                self.session_pool.priority_type.set_type(original_priority_type)
            try:
                session = self.pop_random_session(sessions)
                if not self.session_pool.proxy_condition(session.proxy):
                    session.is_valid = False
                    self._full_size -= self.max_use_per
                    self.session_pool.invalid_sessions.append(session)
                    continue
                
                if not session._prepared:
                    self.session_pool.init_client_session(session)
                
                if not self.handle_max_connections(session):
                    self._max_conn_ids.add(session.id)
                    continue
                else:
                    sessions.append(session)
            finally:
                for s in sessions:
                    heappush(self.session_pool.sessions_heap, s)
                
            if session.is_valid:
                break
        
        if session is not None:
            session.used_count += 1
            self._get_count += 1
        else:
            if try_get >= self.max_try_get:
                raise PoolHandlerError('Max try get session count reached')
            raise QueueEmptyError('SessionPool queue has not available sessions')
        return session
    
    def put(self, session: ClientSession) -> None:
        session.used_count -= 1
        self._get_count -= 1
        if session.id in self._max_conn_ids and (self.handle_max_connections(session) or session.used_count == 0):
            heappush(self.session_pool.sessions_heap, session)
            self._max_conn_ids.remove(session.id)

    def handle_max_connections(self, session: ClientSession) -> bool:
        if self.session_pool.per_session_max_connections == 'auto':
            if session.used_count >= self.session_pool.per_session_max_use:
                return False
            elif session.max_use is None:
                return True
            elif session.used_count < session.max_use:
                return True
        elif session.used_count < self.session_pool.per_session_max_connections:
            return True
        return False

    def change_full_size(self, elapsed: int) -> None:
        self._full_size -= elapsed

class SessionPoolContextManager:
    __slots__ = ('_coro', '_put', '_session')
    def __init__(self, coro, put):
        self._coro = coro
        self._put = put
        self._session = None
    
    async def __aenter__(self) -> ClientSession:
        self._session = await self._coro
        return self._session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session is not None:
            await self._put(self._session)
            self._session = None

class SessionPool(Proxies):
    def __init__(
            self, 
            proxies: Optional[Union[str, list[Proxy]]]=None,
            loop: Optional[asyncio.AbstractEventLoop] = None,
            enabled_accounts_pool: bool = False,
            accounts_pool: Optional[list[AccountsPool]] = None,
            max_ping: Optional[int] = None,
            min_speed: Optional[int] = 1024,
            init_check: bool = True,
            init_check_interval: int = 15*60,
            auto_check: bool = True,
            auto_check_interval: int = 30*60,
            per_session_max_connections: Union[int, str]='auto',
            per_session_max_use: int = 8,
            force_direct_session_max_priority: Optional[bool] = True,
            kwds: dict = None,
        ):
        self.enabled_accounts_pool = enabled_accounts_pool
        self.accounts_pool = accounts_pool or AccountsPool() # default accounts pool
        if self.accounts_pool.session_pool is not None:
            raise ValueError('AccountsPool session_pool is already set')
        self.per_session_max_connections = per_session_max_connections
        self.per_session_max_use = per_session_max_use if per_session_max_connections == 'auto' else per_session_max_connections
        self.max_ping = max_ping
        self.min_speed = min_speed
        self.force_direct_session_max_priority = force_direct_session_max_priority
        
        save_load_manager = SaveLoadManager(ProxiesInfoSaveLoad, ProxiesSaveLoadSP, SessionPoolSaveLoad)
        super().__init__(
            proxies, loop, save_load_manager, 
            init_check=init_check, init_check_interval=init_check_interval,
            auto_check=auto_check, auto_check_interval=auto_check_interval)
        self.save_load_manager.find(SessionPoolSaveLoad).load_once()
        
        self._lock = asyncio.Lock()
        self.proxies_ref = self.proxies
        self.kwds = kwds or self.default_kwds(self._loop)
        self.trace_config = self._get_trace_config()
        
        self.sessions_heap:    list[ClientSession] = []
        self.sessions_raw:     list[ClientSession] = []
        self.invalid_sessions: list[ClientSession] = []
        self._kwds_instances = None
        
        self.init_check_proxies()
        self.fresh_sessions()
        self.handler = PoolHandler(self)
        self.async_queue = AsyncSessionPoolQueue(self.handler, self._loop)

    @staticmethod
    def default_kwds(loop: asyncio.AbstractEventLoop) -> dict:
        return {
            'connector': TCPConnector(ttl_dns_cache=3600, ssl=False, loop=loop),
            'timeout': ClientTimeout(connect=24, sock_connect=24),
        }

    def fresh_sessions(self):
        def set_direct_session_priority(session: ClientSession) -> ClientSession:
            if session.proxy.is_direct_proxy and self.force_direct_session_max_priority:
                session.proxy.force_priority = INT64MAX if self.priority_type.sequence_positive() else 0
            return session
        self.add_direct_proxy()
        self.sessions_heap = [set_direct_session_priority(ClientSession(i, proxy)) for i, proxy in enumerate(self.proxies)]
        self.sessions_raw = self.sessions_heap.copy()
        if self.enabled_accounts_pool:
            self._accounts = self.accounts_pool.accounts.copy()
        self.heapify_sessions()
    
    def heapify_sessions(self):
        if len(self.sessions_heap) > 1:
            heapify(self.sessions_heap)
    
    async def check_proxies(self, *args, **kwargs):
        res = await super().check_proxies(*args, **kwargs)
        self.heapify_sessions()
        return res
    
    def get(self, priority_type: Optional[str] = None, **kwds: dict) -> SessionPoolContextManager:
        return SessionPoolContextManager(self._get(priority_type=priority_type, **kwds), self.put)
    async def _get(self, **get_kwds: dict) -> ClientSession:
        async with self._lock:
            return await self.async_queue.get(**get_kwds)
    def get_nowait(self, **get_kwds: dict) -> ClientSession:
        return self.async_queue.get_nowait(**get_kwds)
    
    async def put(self, session: ClientSession):
        await self.async_queue.put(session)
    async def put_nowait(self, session: ClientSession):
        self.async_queue.put_nowait(session)
    
    def proxy_condition(self, proxy: Proxy) -> bool:
        if not proxy.is_valid:
            return False
        elif proxy.ping is not None and self.max_ping is not None and proxy.ping > self.max_ping:
            return False
        elif proxy.speed is not None and self.min_speed is not None and proxy.speed < self.min_speed:
            return False
        return True

    @property
    def kwds_instances(self) -> dict:
        if self._kwds_instances is None:
            self._kwds_instances = self._kwds_parse(self.kwds.copy())
        return self._kwds_instances

    @staticmethod
    def _kwds_parse(kwds: dict):
        if connector := kwds.get('connector'):
            if isinstance(connector, dict):
                # default connector is TCPConnector
                kwds['connector'] = TCPConnector(**kwds['connector'])
            elif not isinstance(connector, (TCPConnector, UnixConnector, NamedPipeConnector)):
                raise TypeError('kwds.connector must be dict or aiohttp.BaseConnector instance.')
        if timeout := kwds.get('timeout'):
            if isinstance(timeout, dict):
                kwds['timeout'] = ClientTimeout(**kwds['timeout'])
            elif isinstance(timeout, int):
                kwds['timeout'] = ClientTimeout(total=timeout)
            elif not isinstance(timeout, ClientTimeout):
                raise TypeError('kwds.timeout must be int, dict or ClientTimeout instance.')
        return kwds
    
    def kwds_prepare(self, kwds: dict):
        if self.kwds is not None:
            for k, v in self.kwds.items():
                if k not in kwds:
                    kwds[k] = v
    
    def init_client_session(self, session: ClientSession, **kwds: dict) -> None:
        if kwds:
            self.kwds_prepare(kwds)
            kwds = self._kwds_parse(kwds.copy())
        else:
            kwds = self.kwds_instances
        if self.enabled_accounts_pool:
            try:
                acc = self._accounts.pop()
            except:
                acc = None
            session.kemono_account = acc
        session.init(loop=self._loop, trace_configs=[self.trace_config], headers=UA_RAND.headers.get(), **kwds)
        
    def _get_trace_config(self) -> TraceConfig: 
        # call back for exception
        async def on_request_exception(
                session: ClientSession, 
                trace: Union[TraceConfig, List[TraceConfig]], 
                params: TraceRequestExceptionParams):
            if isinstance(params.exception, (Exception)):
                pass
        async def on_request_end(
                session: ClientSession, 
                trace: Union[TraceConfig, List[TraceConfig]], 
                params: TraceRequestEndParams):
            if params.response.status == 429:
                async with self.handler._lock:
                    max_use = min(max(1, session.used_count - 1), self.per_session_max_use)
                    if session.max_use is None:
                        elapsed = self.per_session_max_use - max_use
                    else:
                        elapsed = session.max_use - max_use
                    session.max_use = max_use
                    # reset cache and update full_size
                    self.handler.change_full_size(elapsed)

        conf = TraceConfig()
        # conf.on_request_exception.append(on_request_exception)
        conf.on_request_end.append(on_request_end)

        return conf

    def load(self, data: dict, instance: BaseSaveLoad) -> None:
        if isinstance(instance, (ProxiesInfoSaveLoad, ProxiesSaveLoadSP)):
            return super().load(data, instance)
        elif isinstance(instance, SessionPoolSaveLoad):
            self.update(**data)
    
    def dump(self, instance: BaseSaveLoad):
        if isinstance(instance, (ProxiesInfoSaveLoad, ProxiesSaveLoadSP)):
            return super().dump(instance)
        elif isinstance(instance, SessionPoolSaveLoad):
            return self.dump_config()
    
    def dump_config(self):
        return {
            'per_session_max_connections': self.per_session_max_connections,
            'per_session_max_use': self.per_session_max_use,
            'max_ping': self.max_ping,
            'min_speed': self.min_speed,
        }
    
    def __del__(self):
        for session in self.sessions_raw:
            if session is not None and not session.closed:
                # FIXME: This is not safely
                try:
                    session.close().send(None)
                except StopIteration:
                    try:
                        if self._loop.is_running():
                            self._loop.run_until_complete(session.close())
                    except Exception:
                        pass
        self.save_load_manager.auto_save()
        super().__del__()




if __name__ == '__main__':
    pool = SessionPool() # , proxies = "fanqie_01"
    
    pool.full_check_proxies(semaphore=8)
