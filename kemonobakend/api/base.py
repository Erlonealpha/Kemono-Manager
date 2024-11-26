import asyncio
from re import sub
from yarl import URL
from aiohttp import ClientResponse, ClientTimeout
from typing import Any, Callable, Optional

from kemonobakend.session_pool import SessionPool
from kemonobakend.log import logger
from kemonobakend.config import settings


class ApiBuilder:
    @staticmethod
    def build(api: str, path: str, format: dict=None, query: dict=None):
        def remove_none(d: dict):
            return {k: v for k, v in d.items() if v is not None}
        if format:
            path = sub(r'\{(\w+)\}', r'{\1}', path).format(**format)
        url = URL(api) / path.strip('/')
        if query:
            query = remove_none(query)
            url = url.with_query(query)
        return str(url)

class BaseAPI:
    session_pool: SessionPool = None
    
    async def fetch(
            self, 
            url: str, 
            method: str = 'GET', 
            required_status: list = [200, 206],
            retry = 3,
            headers: dict = None, 
            data: dict = None, 
            return_callable: Callable[[ClientResponse], Any] = lambda resp: resp.json(),
            warning: bool = True,
            strict: bool = True,
            **kwargs
        ):
        while retry > 0:
            try:
                async with self.session_pool.get(priority_type="ping") as session:
                    func: Callable[..., Optional[ClientResponse]] = getattr(session, method.lower())
                    timeout = ClientTimeout(total=20, connect=10, sock_connect=10, sock_read=12)
                    async with func(url, allow_redirects=True, headers=headers, data=data, timeout=timeout, **kwargs) as response:
                        if response.status in required_status:
                            res = return_callable(response)
                            if asyncio.iscoroutine(res):
                                res = await res
                            if strict and not res:
                                raise ValueError(f"({retry})Failed to fetch {url}: empty response")
                            return res
                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 1))
                            await asyncio.sleep(retry_after)
                        elif response.status == 404:
                            return None
                        else:
                            if warning:
                                logger.error(f"({retry})Failed to fetch {url}: {response.status} {response.reason}")
            except Exception as e:
                if warning:
                    logger.error(f"({retry})[{e.__class__.__name__}]Failed to fetch {url}: {e}")
            finally:
                retry -= 1

    
    async def fetch_json(self, url: str, retry=3, warning: bool = True, strict: bool = True):
        while retry > 0:
            try:
                async with self.session_pool.get() as session:
                    async with session.get(url, allow_redirects=True) as response:
                        ...
            except Exception as e:
                if warning:
                    logger.error(f"({retry})Failed to fetch {url}: {e}")
            finally:
                try:
                    retry -= 1
                except:
                    pass
    
    def path(self, path: str, format: dict=None, query: dict=None):
        return ApiBuilder.build(self.__api_url__, path, format, query)