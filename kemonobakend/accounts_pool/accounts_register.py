import asyncio
from yarl import URL
from http.cookies import SimpleCookie
from aiohttp import ClientSession, ClientTimeout
from typing import Optional, Union
from kemonobakend.log import logger

def parse_query_string(query_string: str) -> dict:
    if not query_string.startswith("http"):
        url_like = "http://example.com" + query_string
    url = URL(url_like)
    return url.query

class AccountRegister:
    def __init__(self, session_pool = None):
        self.session_pool = session_pool

    async def register_account(self, username: str, password: str, proxy = None) -> bool:
        payload = {
            "favorites": "",
            "location": "/artists",
            "username": username,
            "password": password,
            "confirm_password": password,
        }
        
        async def fetch(session: ClientSession):
            try:
                async with session.post("https://kemono.su/account/register", allow_redirects=False, proxy = proxy, data=payload) as response:
                    if response.status == 302:
                        location = response.headers.get("location", "Location")
                        q = parse_query_string(location)
                        if q.get("logged_in") == "yes":
                            return response.cookies
                    elif response.status == 429:
                        asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error while registering account {username}: {e}")
                return False
            return False
        
        if self.session_pool is not None:
            async with self.session_pool.get() as session:
                return await fetch(session)
        else:
            async with ClientSession(timeout=ClientTimeout(total=16, connect=10, sock_connect=10, sock_read=8)) as session:
                return await fetch(session)
    
    async def login_account(self, username: str, password: str, proxy = None) -> Union[bool, SimpleCookie]:
        payload = {
            "location": "/artists",
            "username": username,
            "password": password,
        }
        
        async def fetch(session: ClientSession):
            try:
                async with session.post("https://kemono.su/account/login", proxy = proxy, allow_redirects=False, data=payload) as response:
                    if response.status == 302:
                        location = response.headers.get("location", "Location")
                        q = parse_query_string(location)
                        if q.get("logged_in") == "yes":
                            return response.cookies
                    elif response.status == 429:
                        asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error while logging in account {username}: {e}")
                return False
            return False
        
        if self.session_pool is not None:
            async with self.session_pool.get() as session:
                return await fetch(session)
        else:
            async with ClientSession(timeout=ClientTimeout(total=16, connect=10, sock_connect=10, sock_read=8)) as session:
                return await fetch(session)

    async def register_accounts_auto(self, root: str, nums: int, max_workers: int = 16):
        if len(root) > 15:
            raise ValueError("Root too long")
        usernames = [f"{root}{hex(int("1" + str(i).zfill(2)))}" for i in range(nums)]
        if len(usernames[-1]) > 15:
            raise ValueError("Username too long")
        
        async def semaphore_wrap(semaphore, task):
            async with semaphore:
                return await task
        
        semaphore = asyncio.Semaphore(max_workers)
        tasks = [
            asyncio.create_task(semaphore_wrap(semaphore, self.register_account(username, username)))
            for username in usernames
        ]
        results = await asyncio.gather(*tasks)
        return results
    
    async def login_accounts_auto(self, root: str, nums: int, max_workers: int = 16):
        if len(root) > 15:
            raise ValueError("Root too long")
        usernames = [f"{root}{hex(int("1" + str(i).zfill(2)))}" for i in range(nums)]
        if len(usernames[-1]) > 15:
            raise ValueError("Username too long")
        
        async def semaphore_wrap(semaphore, task):
            async with semaphore:
                return await task
        
        semaphore = asyncio.Semaphore(max_workers)
        tasks = [
            asyncio.create_task(semaphore_wrap(semaphore, self.login_account(username, username)))
            for username in usernames
        ]
        results = await asyncio.gather(*tasks)
        return results
    
    
