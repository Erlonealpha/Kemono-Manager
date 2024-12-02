import asyncio
from re import sub
from yarl import URL
from aiohttp import ClientResponse, ClientTimeout
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional, Coroutine

from kemonobakend.session_pool import SessionPool
from kemonobakend.kemono.builtins import get_service_site
from kemonobakend.log import logger
from kemonobakend.config import settings


class PartySuAPIError(Exception):
    """Base class for PartySu API errors."""

class PartySuAPIInvalidResponse(PartySuAPIError):
    """Invalid response from PartySu API."""

class PartySuAPIInvalidJSON(PartySuAPIError):
    """Invalid JSON response from PartySu API."""

class NotFoundError(PartySuAPIError):
    """Resource not found."""

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
    __api_url_map__: dict
    
    async def fetch(
        self, 
        url: str, 
        return_callable: Optional[Callable[[ClientResponse], Coroutine[None, None, Any]]] = None,
        method: str = 'GET', 
        required_status: list[int] = [200],
        retry = 3,
        headers: dict = None, 
        data: dict = None, 
        warning: bool = True,
        **kwargs
    ):
        if return_callable is None:
            async def _return_callable(resp: ClientResponse):
                return await resp.json()
            return_callable = _return_callable
        while retry > 0:
            async with self.session_pool.get(priority_type="ping") as session:
                func: Callable[..., Optional[ClientResponse]] = getattr(session, method.lower())
                timeout = kwargs.pop("timeout", None) or ClientTimeout(total=20, connect=10, sock_connect=10, sock_read=12)
                try:
                    async with func(
                        url, allow_redirects=kwargs.pop("allow_redirects", True), 
                        headers=headers, data=data, timeout=timeout, **kwargs
                    ) as response:
                        if response.status in required_status:
                            res = await return_callable(response)
                            if isinstance(res, bool):
                                continue
                            return res
                        elif response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 1))
                            await asyncio.sleep(retry_after)
                        elif response.status == 404:
                            if warning:
                                logger.warning(f"({retry})Failed to fetch {url}: {response.status} {response.reason}")
                            return None
                        elif response.status >= 500:
                            if warning:
                                logger.warning(f"({retry})Failed to fetch {url}: {response.status} {response.reason}")
                except NotFoundError as e:
                    if warning:
                        logger.warning(f"({retry})Failed to fetch {url}: {e}")
                    return None
                except Exception as e:
                    if warning:
                        logger.error(f"({retry})[{e.__class__.__name__}]Failed to fetch {url}: {e}")
                finally:
                    retry -= 1
        return None
    
    async def fetch_content(
            self, 
            url: str, 
            method: str = 'GET', 
            required_status: list[int] = [200, 206],
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

    
    def path(self, path: str, site_or_service, *, format: dict=None, query: dict=None):
        site = get_service_site(site_or_service)
        api_url = self.__api_url_map__.get(site)
        return ApiBuilder.build(api_url, path, format, query)