from os import listdir
from os.path import exists, abspath, splitext, dirname
from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop, Semaphore, gather, wait as asyncio_wait, wait_for as asyncio_wait_for
from concurrent.futures import Future
from aiohttp import ClientTimeout
from time import time as current_time
from datetime import datetime
from rich import print
from inspect import currentframe
from apscheduler.triggers.interval import IntervalTrigger

from kemonobakend.utils.ext import AsyncIOScheduler
from kemonobakend.config import settings
from kemonobakend.utils import InputSetMeta, json_load, json_dump, to_unit
from kemonobakend.utils.helpers import get_running_loop
from .proxy import Proxy, PriorityType, CheckProxyCallbackParams, FreshProxyInfoCallbackParams


from typing import (
    Union, Type, Optional, Coroutine, Callable, MutableSet,
    Any
)

def is_abs_path(path: str):
    return abspath(path).replace('\\', '/') == path.replace('\\', '/')

class AbstractSaveLoadModel(metaclass=InputSetMeta):
    auto_save: bool
    _input_set: set[str]
    @property
    def input_set(self) -> set[str]: ...
    @input_set.setter
    def input_set(self, value: Union[set[str], MutableSet[str]]):...
    def dump(self, instance: 'BaseSaveLoad') ->      Union[list, dict]:          raise NotImplementedError
    def load(self, data:   Union[list, dict], instance: 'BaseSaveLoad') -> None: raise NotImplementedError
    def update(self, kwargs: dict) -> None: raise NotImplementedError

class BaseSaveLoadModel(AbstractSaveLoadModel):
    auto_save: bool = True
    _input_set: set[str] = None
    @property
    def input_set(self) -> set[str]: 
        if self._input_set is None:
            self._input_set = set()
        return self._input_set
    @input_set.setter
    def input_set(self, value: Union[set[str], MutableSet[str]]): 
        if value is None:
            value = set()
        if not isinstance(value, set):
            value = set(value)
        self._input_set = value
    def update(self, **kwargs: dict) -> None:
        for k, v in kwargs.items():
            if k not in self.input_set:
                if hasattr(self, k):
                    setattr(self, k, v)
                elif hasattr(self.__class__, k):
                    setattr(self.__class__, k, v)


class BaseSaveLoadMeta(type):
    def __new__(cls, name, bases, attrs):
        if 'save_path' not in attrs:
            raise AttributeError(f"Class {name} doesn't have attribute'save_path'")
        return super().__new__(cls, name, bases, attrs)
class BaseSaveLoad(metaclass=BaseSaveLoadMeta):
    save_path: str = None
    priority: int = 100
    def __init__(self, instance: BaseSaveLoadModel):
        self.instance = instance
        self._loaded = False

    def load(self):
        data = self._load()
        if data is not None:
            self.instance.load(data, self)
        self._loaded = True
    def load_once(self):
        if not self._loaded:
            self.load()

    def save(self):
        data = self.instance.dump(self)
        if data is not None:
            self._save(data)
    def auto_save(self):
        if self.instance.auto_save:
            self.save()
    
    def _load(self) -> dict[str, Any]:
        if not exists(self.save_path):
            return None
        return json_load(self.save_path)
    def _save(self, data):
        json_dump(data, self.save_path)
    
    def __lt__(self, other: 'BaseSaveLoad'):
        if isinstance(other, BaseSaveLoad):
            priority = self.priority
        elif isinstance(other, int):
            priority = other
        else:
            raise TypeError(f"Unsupported type of other: {type(other)}")
        return priority < other.priority

class ProxiesSaveLoad(BaseSaveLoad):
    priority = 0
    save_path = "data/cache/proxies.json"

class ProxiesInfoSaveLoad(BaseSaveLoad):
    save_path = "data/cache/proxies_info.json"
    def save(self):
        data = self.instance.dump(self)
        if data is not None:
            old = json_load(self.save_path)
            if old is None:
                old = {}
            old.update(data)
            self._save(old)

class AbsSaveLoadWarning:
    def load(self):
        self._warning()
    def save(self):
        self._warning()
    def auto_save(self):
        self._warning()
    def _load(self):
        self._warning()
    def _save(self):
        self._warning()
    def _warning(self):
        print('[yellow]Warning: [red]Called method of AbsSaveLoadWarning, find a None object.[/]')

class SaveLoadManager:
    def __init__(self, *save_load_cls: Type[BaseSaveLoad]):
        if not save_load_cls:
            save_load_cls = (ProxiesInfoSaveLoad, ProxiesSaveLoad)
        self.save_load_cls = save_load_cls
        self.save_load_instances: list[BaseSaveLoad] = []
        self._init = False
    
    def init(self, instance: BaseSaveLoad) -> 'SaveLoadManager':
        self._init = True
        self._check_instance(instance)
        self.save_load_instances = sorted([
            save_load_cls(instance=instance) for save_load_cls in self.save_load_cls
        ])
        return self
    
    def __call__(self, instance: BaseSaveLoad) -> 'SaveLoadManager':
        return self.init(instance)

    @staticmethod
    def _check_instance(instance: BaseSaveLoad):
        if issubclass(instance.__class__, BaseSaveLoadModel):
            return
        attrs = [attr for attr in dir(BaseSaveLoadModel) if not attr.startswith('__')]
        for attr in attrs:
            if not hasattr(instance, attr):
                raise AttributeError(f"Class {instance.__class__.__name__} doesn't have attribute {attr}")
    def load(self):
        self._not_init()
        for save_load in self.save_load_instances:
            save_load.load()
    def save(self):
        self._not_init()
        for save_load in self.save_load_instances:
            save_load.save()
    def auto_save(self):
        self._not_init()
        for save_load in self.save_load_instances:
            save_load.auto_save()
    
    def find(self, cls: Type[BaseSaveLoad]) -> Union[BaseSaveLoad, AbsSaveLoadWarning]:
        '''
        This method is used to find a specific save_load instance by class type.
        It safely returns an AbsSaveLoadWarning object if the instance is not found.
        '''
        for save_load in self.save_load_instances:
            if isinstance(save_load, cls):
                return save_load
        return AbsSaveLoadWarning()
    
    def _not_init(self):
        if not self._init:
            raise ValueError('SaveLoadManager is not initialized, please call it with an instance of BaseSaveLoad')

class Proxies(BaseSaveLoadModel):

    _last_checked: Optional[datetime] = None
    _proxies: list[Proxy] = None
    _priority_type: PriorityType = None
    save_load_manager = None
    
    def __init__(
            self, 
            proxies: Optional[Union[str, list[Union[dict, Proxy]]]] = None,
            loop: Optional[AbstractEventLoop] = None,
            save_load_manager: SaveLoadManager = None, 
            init_check: bool = True,
            init_check_interval: int = 60*15,
            auto_check: bool = True,
            auto_check_interval: int = 60*30,
        ):
        self.init_check = init_check
        self.init_check_interval = init_check_interval
        self.auto_check = auto_check
        self.auto_check_interval = auto_check_interval
        
        self._loop = get_running_loop(loop)
        
        if save_load_manager is None:
            save_load_manager = self.default_save_load_manager()
        self.save_load_manager = save_load_manager.init(self)
        
        self.proxies = proxies
        self.save_load_manager.find(ProxiesSaveLoad).load_once()
        self.save_load_manager.find(ProxiesInfoSaveLoad).load_once()
        
        if not self.proxies:
            self.proxies = self.load_default_proxies()
            if not self.proxies:
                self.add_direct_proxy()
        self.auto_check_proxies_scheduler = AsyncIOScheduler()
        if self.auto_check:
            self.auto_check_proxies_scheduler.add_job(self.auto_check_proxies, trigger=IntervalTrigger(seconds=self.auto_check_interval))
            self.auto_check_proxies_scheduler.start(loop=self._loop)
        
        self._init_check_proxies_task = None
        self.init_check_proxies()
    
    def is_outermost_class(self):
        frame = currentframe()
        now_cls = frame.f_back.f_back.f_code.co_qualname.split('.')[0]
        out_cls = self.__class__.__mro__[0].__name__
        return now_cls == out_cls
    def save_load_manager_first_load(self) -> bool:
        '''
        first call save_load_manager.load() in the outermost class
        '''
        if self.save_load_manager is None:
            raise Exception('SaveLoadManager is not initialized')
        frame = currentframe()
        func = frame.f_back.f_code.co_name
        if func != "__init__":
            raise Exception("This method only can be called by __init__ method")
        co_qualname = frame.f_back.f_code.co_qualname.split('.')
        now_space_class_name = co_qualname[0]
        outermost_class_name = self.__class__.__mro__[0].__name__
        
        if now_space_class_name == outermost_class_name:
            self.save_load_manager.load()
            return True
        return False
    
        
    @staticmethod
    def default_save_load_manager():
        return SaveLoadManager(ProxiesSaveLoad, ProxiesInfoSaveLoad)

    # load proxies from file
    def path_check(self, path:str):
        if not is_abs_path(path) and not path.startswith('data/proxies/'):
            ext = splitext(path)[1]
            if ext == '':
                path += '.json'
            path = f'data/proxies/{path}'
        return path
    def load_proxies_file(self, path:str) -> list[Proxy]:
        path = self.path_check(path)
        d = json_load(path)
        if d is not None and isinstance(d, list):
            proxies = [self.proxy_instance(**proxy) for proxy in d]
            return proxies
        return []

    @property
    def proxies(self) -> list[Proxy]:
        return self._proxies
    @proxies.setter
    def proxies(self, value):
        if value is None:
            self._proxies = []
            return
        if isinstance(value, str):
            value = self.load_proxies_file(value)
        elif isinstance(value, list):
            if isinstance(value[0], dict):
                value = [self.proxy_instance(**proxy) for proxy in value]
            elif isinstance(value[0], Proxy):
                value = value
            else:
                raise TypeError(f"Unsupported type of proxies: {type(value[0])}")
        else:
            raise TypeError(f"Unsupported type of proxies: {type(value)}")
        self._proxies = value

    @property
    def priority_type(self) -> PriorityType:
        if self._priority_type is None:
            self._priority_type = PriorityType('speed')
        return self._priority_type
    @priority_type.setter
    def priority_type(self, value):
        if isinstance(value, str):
            if self._priority_type is None:
                self._priority_type = PriorityType(value)
            else:
                self._priority_type.set_type(value)
        else:
            self._priority_type = value

    @property
    def last_checked(self):
        return self._last_checked
    @last_checked.setter
    def last_checked(self, value):
        if isinstance(value, str):
            value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        self._last_checked = value
    
    async def wait_init_check_proxies(self):
        if self._init_check_proxies_task is not None:
            await asyncio_wait_for(self._init_check_proxies_task, timeout=None)
            self._init_check_proxies_task = None
    
    def init_check_proxies(self):
        if self.init_check and self.is_outermost_class():
            if self.last_checked is None or (datetime.now() - self.last_checked).total_seconds() > self.init_check_interval:
                self._init_check_proxies_task = self._loop.create_task(self.full_check_proxies())

    async def auto_check_proxies(self):
        if self.last_checked is None or (datetime.now() - self.last_checked).total_seconds() > self.auto_check_interval:
            await self.full_check_proxies(output=False, semaphore=6)
    
    async def check_proxies(
            self, 
            wait: bool = True,
            auto_save: bool = True,
            output: bool = True,
            proxies: Optional[list[Proxy]] = None,
            target_url:str = None,
            timeout: Optional[ClientTimeout] = None,
            semaphore: Optional[Union[Semaphore, int]] = None,
            callback: Callable[[], Any] = None,
            callback_multi: Callable[[Proxy, CheckProxyCallbackParams], Any] = None
        ):
        def _callback(proxy: Proxy, params: CheckProxyCallbackParams):
            nonlocal c
            c += 1
            if output:
                conn = f"{params.connection_time:.2f}" if params.connection_time is not None else ' N/A'
                read = f"{params.read_time:.2f}" if params.read_time is not None else ' N/A'
                if params.success:
                    print( f"[green]Speed: {to_unit(params.speed, keep_length=6)}/s\tPing: {conn}\tRead time: {read}\t\t{proxy.name}[/green]")
                elif params.exception is not None:
                    print(   f"[red]Speed: {to_unit(params.speed, keep_length=6)}/s\tPing: {conn}\tRead time: {read}\t\t{proxy.name}\t\tException: {params.exception.__class__.__name__}[/red]")
                else:
                    print(f"[yellow]Speed: {to_unit(params.speed, keep_length=6)}/s\tPing: {conn}\tRead time: {read}\t\t{proxy.name}\t\tStatus: {params.response.status}[/yellow]")
            if callback_multi is not None:
                callback_multi(proxy, params)
            if c == l:
                if output:
                    print(f"All has been done in {current_time() - t0:.2f} seconds.")
                if callback is not None:
                    callback()
                self.last_checked = datetime.now()
                if auto_save:
                    self.save_load_manager.find(ProxiesSaveLoad).auto_save()
        if isinstance(semaphore, int):
            semaphore = Semaphore(semaphore)
        if not proxies:
            proxies = self.proxies
        c = 0
        l = len(proxies)
        if output:
            t0 = current_time()

        tasks = [
                proxy.check(
                    timeout=timeout, target_url=target_url, callback=_callback, semaphore=semaphore
            ) for proxy in proxies
        ]
        
        f = gather(*tasks)
        
        if wait:
            return await f
        return f

    async def fresh_proxies_info(
            self, 
            wait: bool = True, 
            auto_save: bool = True,
            show_time: bool = True,
            callback: Callable[[], Any] = None,
            callback_multi: Callable[[Proxy, FreshProxyInfoCallbackParams], Any] = None
        ):
        def _callback(proxy: Proxy, params: FreshProxyInfoCallbackParams):
            nonlocal c
            c += 1
            if callback_multi is not None:
                callback_multi(proxy, params)
            
            if show_time:
                print(f'Getting info of proxy {c}/{p_len} {proxy.name}\t\t\t\t', end='\r')
                if params.exception is not None:
                    pass
            if c == p_len: 
                if show_time:
                    print(f'\nAll has been done in {current_time() - t0:.2f} seconds.')
                if auto_save:
                    self.save_load_manager.find(ProxiesInfoSaveLoad).auto_save()
                if callback is not None:
                    callback()
        c = 0
        p_len = len(self.proxies)
        if show_time:
            t0 = current_time()
        
        tasks = [
            proxy.fresh_info(callback=_callback)
            for proxy in self.proxies
        ]
        
        future = gather(*tasks)
        
        if wait:
            return await future
        return future
    
    async def full_check_proxies(
            self, 
            wait: bool = True,
            auto_save: bool = True,
            proxies: Optional[list[Proxy]] = None,
            target_url:str = None,
            semaphore: Optional[Union[Semaphore, int]] = 16,
            timeout: Optional[ClientTimeout] = None,
            output: bool = True,
            callback: Callable[[], Any] = None
        ):
        _f0 = await self.fresh_proxies_info(wait=False, auto_save=auto_save, show_time=output)
        if proxies is None:
            proxies = self.proxies
        await _f0
        _f1 = await self.check_proxies(
            wait=False, auto_save=auto_save, output=output, proxies=proxies, 
            target_url=target_url, timeout=timeout, semaphore=semaphore, callback=callback)
        if wait:
            return await _f1
        return _f1
    
    async def test(self):
        urls = [
            "https://webapi-pc.meitu.com/common/ip_location",
            "https://www.ip.cn/api/index?ip=&type=0",
            "https://whois.pconline.com.cn/ipJson.jsp?ip=&json=true",
            "https://api.vore.top/api/IPdata?ip=",
            "https://api.ip.sb/geoip/",
            "https://api.ip2location.io/",
            "https://realip.cc/",
            "http://demo.ip-api.com/json/?lang=zh-CN",
            "https://ip-api.io/json",
            "https://ipapi.co/json/",
            "https://api.ipapi.is",
            "https://api.ip.sb/geoip",
            "https://api.qjqq.cn/api/Local",
            "https://ip.useragentinfo.com/json",
            "http://httpbin.org/ip",
            "https://cdid.c-ctrip.com/model-poc2/h",
            "https://vv.video.qq.com/checktime?otype=ojson",
            "https://api.uomg.com/api/visitor.info?skey=1",
            "https://test.ipw.cn/api/ip/myip?json",
            "https://api.ipify.org",
            "https://ipv4.my.ipinfo.app/api/ipDetails.php",
            "https://g3.letv.com/r?format=1",
        ]
        proxy = self.proxies[14]
        tasks = [
            proxy.fresh_info(url)
            for url in urls
        ]
        f = await gather(*tasks)
        return f

    @staticmethod
    def load_default_proxies():
        if settings.proxies.default_proxies is not None:
            return settings.proxies.default_proxies
        if exists('data/proxies'):
            lst = listdir('data/proxies')
            for file in lst:
                d = json_load(f'data/proxies/{file}')
                if d is not None and isinstance(d, list):
                    return d
        return []

    @property
    def is_contain_none_proxy(self): 
        # 是否包含空代理，用于代理池且包含不使用代理
        return any(proxy.is_direct_proxy for proxy in self.proxies)
    
    def add_none_proxy(self):
        if not self.is_contain_none_proxy:
            self.proxies.append(self.proxy_instance())
    
    def add_direct_proxy(self):
        # alias of add_none_proxy
        return self.add_none_proxy()

    def proxy_instance(self, *args, **kwargs):
        return Proxy(priority_type=self.priority_type, *args, **kwargs)

    def dump(self, instance: 'BaseSaveLoad'):
        if isinstance(instance, ProxiesInfoSaveLoad):
            return self.dump_info()
        elif isinstance(instance, ProxiesSaveLoad):
            return self.dump_proxies_config()
    def load(self, data: Union[list, dict], instance: 'BaseSaveLoad') -> None:
        if isinstance(instance, ProxiesInfoSaveLoad):
            self.load_info(data)
        elif isinstance(instance, ProxiesSaveLoad):
            self.load_proxies_config(data)
    
    def dump_proxies_config(self):
        return {
            "proxies": [proxy.dump() for proxy in self.proxies],
            "init_check": self.init_check,
            "init_check_interval": self.init_check_interval,
            "auto_check": self.auto_check,
            "auto_check_interval": self.auto_check_interval,
            "priority_type": self.priority_type.get_type(),
            "last_checked": self.last_checked.strftime('%Y-%m-%d %H:%M:%S') if self.last_checked is not None else None,
        }
    
    def load_proxies_config(self, data: dict):
        if data and isinstance(data, list):
            self.proxies = [self.proxy_instance(**proxy) for proxy in data]
            return
        self.update(**data)
    
    def dump_info(self):
        dic = {}
        for proxy in self.proxies:
            if proxy.ip is not None:
                dic[proxy.ip] = proxy.dump_runtime()
                dic[proxy.ip]["info"] = proxy.info
        return dic
    
    def load_info(self, data: dict):
        for proxy in self.proxies:
            if proxy.ip in data:
                info: dict = data.get(proxy.ip)
                last_checked = info.get("last_checked")
                if last_checked is not None and proxy.last_checked is not None \
                    and proxy.last_checked > datetime.strptime(last_checked, '%Y-%m-%d %H:%M:%S'):
                    # only update if the last_checked is newer
                    info = {"info": info.get("info")}
                proxy.update(**info)
    
    def __del__(self):
        try:
            self.auto_check_proxies_scheduler.shutdown()
        except RuntimeError:
            pass

class _Futures:
    def __init__(self, futures: list[Future]):
        self.futures = futures
    def join(self):
        for future in self.futures:
            future.result()
