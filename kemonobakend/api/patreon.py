import asyncio
from aiohttp import ClientResponse, ClientTimeout
from concurrent.futures import Future
from yarl import URL
from re import sub
from json import JSONDecodeError, loads
from bs4 import BeautifulSoup

from rich import print
from typing import Optional, Awaitable, Callable, TypeVar, Union, Any

from kemonobakend.kemono.builtins import KEMONO_SERVICES, KEMONO_API_URL
from kemonobakend.session_pool import SessionPool
from kemonobakend.event_loop import EventLoop, get_event_loop
from kemonobakend.utils.aiotools import pre_gather_tasks, pre_task
from kemonobakend.log import logger
from kemonobakend.config import settings

from .base import BaseAPI

class BasePatreonAPI(BaseAPI):
    def __init__(self, session_pool: SessionPool):
        self.session_pool = session_pool
    
    async def get_creator_details(self, creator_id: str):
        pass

class PatreonAPI(BasePatreonAPI):
    pass