if __name__ == '__main__':
    from os import getcwd
    from sys import path
    path.append(getcwd())

from aiohttp import (
    ClientSession, ClientTimeout, ClientResponse, ClientConnectorError, 
    TraceConfig, TraceConnectionCreateEndParams, ContentTypeError)
from asyncio import Semaphore, sleep, run
from yarl import URL
from datetime import datetime
from time import time as current_time
from rich import print
from typing import NewType, Optional
from json import loads
import attr

from typing import (
    Union, Optional, Callable,
    Any
)

from kemonobakend.config import settings
from kemonobakend.log import logger
from kemonobakend.utils import IdGenerator, UA_RAND

ProxyID = NewType("ProxyID", int)

PRIORITY_TYPES = ["speed", "ping", "response_time", "manual"]

PRIORITY_TYPE_SEQUENCE_MAP = {   
    "speed":         True,
    "ping":          False,
    "response_time": False,
    "manual":        False,
}

class PriorityTypeMeta(type):
    def __call__(self, *args: Any, **kwds: Any) -> Any:
        if args:
            value = args[0]
        else:
            value = kwds.get("value")
        if isinstance(value, PriorityType):
            return value
        return super().__call__(*args, **kwds)

class PriorityType(metaclass=PriorityTypeMeta):
    _type = "speed"
    _types = PRIORITY_TYPES
    def __init__(self, value: Optional[str]=None):
        if not value:
            value = "speed"
        self.set_type(value)

    @classmethod
    def get_types(cls):
        return cls._types

    def set_type(self, value):
        if value in self._types:
            self._type = value
        else:
            raise ValueError(f"Invalid priority type: {value}")

    def get_type(self):
        return self._type
    
    def sequence_positive(self) -> bool:
        '''
        True:  positive sequence
        False: negative sequence
        '''
        return PRIORITY_TYPE_SEQUENCE_MAP[self._type]

    def __eq__(self, value: object) -> bool:
        if isinstance(value, PriorityType):
            value = value.get_type()
        return self._type == value

    def __str__(self):
        return self._type

    def __repr__(self):
        return f"<PriorityType {self._type}>"

    def dump(self):
        return self._type

class ProxyUrl:
    def __init__(self, url, username, password, protocol, **kwargs):
        if url is None: 
            url = self._get_url(kwargs)
        self._url = URL(url) if url else None
        self.username = username
        self.password = password
        self.protocol = protocol or self._url.scheme if self._url else None
        self.kwargs = kwargs

    @staticmethod
    def _get_url(kwargs: dict):
        for key in ["url", "http", "https"]:
            url = kwargs.get(key)
            if url:
                return url
        return None

    @property
    def url(self):
        if not self._url:
            return None
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.url_no_scheme}"
        return str(self._url)
    @url.setter
    def url(self, value):
        if value is None:
            self._url = None
        else:
            self._url = URL(value)

    @property
    def url_no_scheme(self):
        if not self._url:
            return None
        return str(self._url.with_scheme(""))
    
    def __str__(self):
        if not self._url:
            return ""
        return str(self._url)

class _Priority:
    def __init__(
        self,
        proxy: "Proxy",
    ):
        self._proxy = proxy

    @staticmethod
    def _lt_gt(v1, v2, lt=True):
        def _lt(v1, v2):
            return v1 < v2
        def _gt(v1, v2):
            return v1 > v2
        if v1 is None and v2 is not None:
            return lt
        elif v1 is not None and v2 is None:
            return not lt
        elif v1 is None and v2 is None:
            return True
        else:
            if lt:
                return _lt(v1, v2)
            else:
                return _gt(v1, v2)
    
    def _lt_gt_(self, other: 'Proxy', lt: bool = True):
        try:
            if self._proxy.priority_type.sequence_positive() and lt:
                priority = -self._proxy.priority if self._proxy.priority is not None else None
                other_priority = -other.priority if other.priority is not None else None
            else:
                priority = self._proxy.priority
                other_priority = other.priority
            if self._proxy.priority_type == other.priority_type:
                return self._lt_gt(priority, other_priority, lt)
            else:
                return self._lt_gt(priority, other_priority, lt)
        except Exception as e:
            # logger.debug(f"Error comparing proxy: {e}")
            return not lt
    
    def __lt__(self, other: 'Proxy'):
        return self._lt_gt_(other, True)
    
    def __gt__(self, other: 'Proxy'):
        return self._lt_gt_(other, False)


@attr.s(auto_attribs=True, slots=True)
class CheckProxyCallbackParams:
    success: bool = False
    all_time: float = None
    connection_time: float = None
    response_time: float = None
    read_time: float = None
    speed: float = None
    response: ClientResponse = None
    exception: Optional[Exception] = None

@attr.s(auto_attribs=True, slots=True)
class FreshProxyInfoCallbackParams:
    success: bool = False
    info: dict = None
    exception: Optional[Exception] = None
    

class Proxy:
    
    _ip_info_api: str = "https://api.ipapi.is"
    _ip_info_apis: list = [
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
    info: dict = None
    ping = None
    speed = None
    response_time = None
    connection_create_time = None
    
    def __init__(
        self, url:     str|None = None, 
        username:      str|None = None, 
        password:      str|None = None,
        protocol:      str|None = None,
        proxy_name:    str      = "未指定",
        country:       str|None = None,
        region:        str|None = None,
        priority:      int = 0,
        priority_type: str = "speed",
        manual_priority_ascending = True,
        **kwargs
    ):
        self._proxy_url = ProxyUrl(url, username, password, protocol, **kwargs)
        self.name = proxy_name if not self.is_direct_proxy else "Direct"
        self.country = country
        self.region = region
        self._priority = priority
        self.force_priority = None
        self.priority_type = PriorityType(priority_type)
        self.manual_priority_ascending = manual_priority_ascending

        self.info = {}
        self._is_valid = False
        self._last_checked = None
        self._is_using = False
        self.using_count = 0
        self.is_check_running = False
        self.update(**kwargs)
        if self.is_direct_proxy:
            self.is_valid = True
        
        self._priority_instance = _Priority(self)
        self.id:ProxyID = IdGenerator.generate("Proxy")

    @property
    def is_direct_proxy(self):
        return not self.url

    @property
    def url(self):
        return self._proxy_url.url
    @url.setter
    def url(self, value):
        self._proxy_url.url = value

    @property
    def priority(self) -> int:
        if self.force_priority is not None:
            return self.force_priority
        p = getattr(self, self.priority_type.get_type(), None)
        if p is None:
            return self._priority
        return p
    @priority.setter
    def priority(self, value):
        self._priority = value

    @property
    def ip(self) -> Optional[str]:
        return self.info.get("ip")
    @ip.setter
    def ip(self, value):
        self.info["ip"] = value

    def __lt__(self, other: 'Proxy'):
        return self._priority_instance.__lt__(other)
    
    def __gt__(self, other: 'Proxy'):
        return self._priority_instance.__gt__(other)
    
    def __eq__(self, value: object) -> bool:
        if isinstance(value, Proxy):
            return self.id == value.id
        return self.url == value
    def __repr__(self) -> str:
        return f"<Proxy {self.name} {self.url}>"
    @property
    def last_checked(self):
        return self._last_checked
    @last_checked.setter
    def last_checked(self, value):
        if isinstance(value, str):
            value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        self._last_checked = value
    @property
    def is_valid(self):
        return self._is_valid
    @is_valid.setter
    def is_valid(self, value):
        self._is_valid = value
        # 在使用中时，哪怕失效，也不应该被将其设置为None. 由using->unused时再设置
        if not value and not self.is_using:
            self.ping = None
            self.speed = None
            self.response_time = None
    @property
    def is_using(self):
        return self.using_count > 0
    
    def update(self, **kwargs: dict):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def dump(self):
        return {
            "ip": self.ip,
            "url": self.url,
            "username": self._proxy_url.username,
            "password": self._proxy_url.password,
            "protocol": self._proxy_url.protocol,
            "name": self.name,
            "region": self.region,
            "priority": self.priority,
            "manual_priority_ascending": self.manual_priority_ascending,
            "is_valid": self.is_valid,
            "last_checked": self.last_checked.strftime("%Y-%m-%d %H:%M:%S") if self.last_checked else None,
            "ping": self.ping,
            "speed": self.speed,
            "response_time": self.response_time
        }
    def dump_runtime(self):
        return {
            "last_checked": self.last_checked.strftime("%Y-%m-%d %H:%M:%S") if self.last_checked else None,
            "ping": self.ping,
            "speed": self.speed,
            "response_time": self.response_time,
            "connection_create_time": self.connection_create_time
        }
    
    def get_default_priority(self, type: str):
        assert type in PRIORITY_TYPES, "Invalid type"
        if type == "ping":
            return 10
        elif type == "speed":
            return 1024
        elif type == "response_time":
            return 10
    
    def set_priority(self, priority: int):
        self.priority = priority
    def set_priority_type(self, type: PriorityType):
        self.priority_type = type
    
    @staticmethod
    def _get_trace_config(now_time: 'NowTimeShared'):
        async def on_connection_create_end(session, trace_config_ctx, params: TraceConnectionCreateEndParams):
            start_time = now_time.time
            conn_create_time = current_time() - start_time
            now_time.shared_dic["create_end"] = conn_create_time

        trace_conf = TraceConfig()
        trace_conf.on_connection_create_end.append(on_connection_create_end)
        return trace_conf

    async def check(
            self, 
            timeout: Optional[Union[int, ClientTimeout]] = None, 
            target_url: str = "https://img.kemono.su/banners/patreon/5853263", output=True,
            callback: Callable[['Proxy', CheckProxyCallbackParams], Any]=None, 
            no_update: bool=False,
            semaphore: Optional[Semaphore]=None
        ):
        if timeout is None:
            timeout = ClientTimeout(**settings.proxies.proxy_test_timeout)
        if not target_url:
            target_url = "https://n1.kemono.su/data/2b/6b/2b6b81143c42a760e59a155a3bf28bb8ee1d547fdd1ab984711356b34b3df499.jpg"
        if semaphore is None:
            semaphore = Semaphore(1)
        
        async with semaphore:
            self.is_check_running = True
            self.using_count += 1
            retry = 1
            
            if callback is not None:
                callback_params = CheckProxyCallbackParams()

            try:
                now_time = NowTimeShared()
                trace_config = self._get_trace_config(now_time)
                async with ClientSession(timeout=timeout, headers=UA_RAND.headers.get(), trace_configs=[trace_config]) as session:
                    start_time_all = current_time()
                    last_exception = None
                    while retry > 0:
                        try:
                            start_time = now_time.now()
                            async with session.get(target_url, proxy=self.url) as response:
                                if callback is not None:
                                    callback_params.response = response
                                if response.status in [200, 201, 206]:
                                    response_time = current_time() - start_time
                                    self.last_checked = datetime.now()
                                    ping = response.headers.get("X-Response-Time")
                                    connection_create_time = now_time.shared_dic.get("create_end")
                                    if not ping: ping = connection_create_time or response_time
                                    if not no_update:
                                        self.is_valid = True
                                        self.response_time = response_time
                                        self.ping = ping
                                        self.connection_create_time = connection_create_time
                                    speed, content_read = await resp_handle(response)
                                    if not no_update:
                                        self.speed = speed
                                    
                                    if callback is not None:
                                        callback_params.success = True
                                        callback_params.all_time = current_time() - start_time_all
                                        callback_params.connection_time = connection_create_time
                                        callback_params.response_time = response_time
                                        callback_params.read_time = content_read
                                        callback_params.speed = speed
                                        callback_params.success = True
                                    return
                                elif response.status == 429:
                                    retry -= 0.2
                                    await sleep(0.5)
                                else:
                                    if not no_update: 
                                        self.is_valid = False
                                    retry -= 1
                        
                        except (TimeoutError, ClientConnectorError) as e:
                            retry -= 1
                            last_exception = e
                        except Exception as e:
                            last_exception = e
                            retry -= 0.5
                    if not no_update: 
                        self.is_valid = False
                    if callback is not None:
                        callback_params.exception = last_exception
            finally:
                if callback is not None:
                    callback(self, callback_params)
                self.is_check_running = False
                self.using_count -= 1

    async def fresh_info(
            self, api_url: str = None, 
            callback: Callable[['Proxy', FreshProxyInfoCallbackParams], Any]=None
        ):
        def get_ip(dic: dict):
            if "ip" in dic:
                return dic["ip"]
            elif "IP" in dic:
                return dic["IP"]
            elif "host" in dic:
                return dic["host"]
            elif "origin" in dic:
                return dic["origin"]
            elif "ipinfo" in dic:
                return dic.get("ipinfo", {}).get("text")
            elif "data" in dic:
                data = dic["data"]
                if isinstance(data, dict):
                    for k in data.keys():
                        return k
            for v in dic.values():
                if isinstance(v, dict):
                    return get_ip(v)
        if callback is not None:
            callback_params = FreshProxyInfoCallbackParams()
        try:
            info = await self.get_proxy_info(api_url)
            if isinstance(info, dict):
                if "ip" not in info:
                    ip = get_ip(info)
                    if ip:
                        info["ip"] = ip
                    else:
                        info = None
                if info:
                    self.info = info
                    if callback is not None:
                        callback_params.info = info
                        callback_params.success = True
        except Exception as e:
            if callback is not None:
                callback_params.exception = e
        finally:
            if callback is not None:
                callback(self, callback_params)
    
    async def get_proxy_info(self, api_url: str = None, callback: Callable[['Proxy'], Any]=None): 
        timeout = ClientTimeout(3, 2, 2)
        async with ClientSession(headers=UA_RAND.headers.get(), timeout=timeout) as session:
            try:
                if api_url is None:
                    api_url = self._ip_info_api
                async with session.get(api_url, proxy=self.url, ssl=False) as response:
                    if response.status == 200:
                        try:
                            return await response.json()
                        except ContentTypeError:
                            text = await response.text()
                            try:
                                return loads(text)
                            except:
                                return text
                    else:
                        return None
            except Exception as e:
                return e
            finally:
                if callback is not None:
                    callback(self)

class NowTimeShared:
    time = None
    shared_dic = {}
    def now(self):
        self.time = current_time()
        return self.time

async def resp_handle(resp: ClientResponse):
    try:
        t0 = current_time()
        content = await resp.read()
        t1 = current_time()
        t = t1 - t0
        speed = len(content) / t
    except ZeroDivisionError:
        return 0, current_time() - t0
    return speed, t

if __name__ == "__main__":
    proxy = Proxy("http://127.0.0.1:43016", proxy_name="新加坡 V2 | 国内优化1 1倍")
    print(proxy)
    run(proxy.fresh_info())
        
        