import asyncio
from concurrent.futures import Future
from yarl import URL
from re import sub
from bs4 import BeautifulSoup

from rich import print
from typing import Optional, Awaitable, Callable, TypeVar, Union, Any

from kemonobakend.kemono.builtins import user_hash_id_func, post_hash_id_func, SERVICES, API_URL
from kemonobakend.database.models import (
    KemonoCreatorCreate, KemonoUser, KemonoUserCreate, 
    KemonoPostsInfoCreate,
    KemonoAttachmentCreate)
from kemonobakend.database.model_builder import (
    build_kemono_user_by_kwd, build_kemono_creator,
    build_kemono_post,  build_kemono_posts_info,
    get_attachments_kwds_by_post, build_kemono_attachments
)
from kemonobakend.session_pool import SessionPool
from kemonobakend.utils import json_load, json_dump, json_dumps
from kemonobakend.utils.aiotools import pre_gather_tasks, pre_task
from kemonobakend.log import logger
from kemonobakend.config import settings

from .base import BaseAPI

class KemonoAPIError(Exception):
    """Base class for Kemono API errors."""

class KemonoAPIInvalidResponse(KemonoAPIError):
    """Invalid response from Kemono API."""

class KemonoAPIInvalidJSON(KemonoAPIError):
    """Invalid JSON response from Kemono API."""

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

class BaseKemonoAPI(BaseAPI):
    __services__ = SERVICES
    __api_url__ = API_URL
        
    ################################# Posts #################################
    async def list_creators(self) -> list:
        return await self.fetch(self.path(
            '/creators'
        ))
    
    async def list_recent_posts(self, offset: int=0, search_query: str=None):
        return await self.fetch(self.path(
            '/posts',
            query={"o": offset, "q": search_query}
        ))

    async def get_creator_posts(self, service: str, creator_id: str, offset: int=0, search_query: str=None) -> Optional[Union[list[dict], dict]]:
        if offset % 50 != 0:
            raise ValueError("Offset must be a multiple of 50")
        return await self.fetch(self.path(
            "/{service}/user/{creator_id}", 
            {"service": service, "creator_id": creator_id},
            {"o": offset, "q": search_query}),
            required_status=[200, 404]
        )
    
    async def get_creator_posts_legacy(self, service: str, creator_id: str, offset: int=0, search_query: str=None):
        if offset % 50 != 0:
            raise ValueError("Offset must be a multiple of 50")
        return await self.fetch(self.path(
            "/{service}/user/{creator_id}/posts-legacy", 
            {"service": service, "creator_id": creator_id},
            {"o": offset, "q": search_query}),
            required_status=[200]
        )

    async def get_creator_announcements(self, service: str, creator_id: str):
        return await self.fetch(self.path(
            "/{service}/user/{creator_id}/announcements", 
            {"service": service, "creator_id": creator_id}),
            required_status=[200, 404],
            return_callable=lambda resp: resp.json() if resp.status == 200 else resp.text()
        )

    async def get_creator_fancards(self, service: str, creator_id: str):
        if service != "fanbox":
            raise ValueError("Fancards are only available for Fanbox")
        return await self.fetch(self.path(
            "/{service}/user/{creator_id}/fancards", 
            {"service": service, "creator_id": creator_id}),
            required_status=[200, 404],
            return_callable=lambda resp: resp.json() if resp.status == 200 else resp.text()
        )

    async def get_specific_post(self, service: str, creator_id: str, post_id: str):
        return await self.fetch(self.path(
            "/{service}/user/{creator_id}/post/{post_id}", 
            {"service": service, "creator_id": creator_id, "post_id": post_id}),
            required_status=[200, 404],
            return_callable=lambda resp: resp.json() if resp.status == 200 else resp.text()
        )

    async def list_posts_revisions(self, service: str, creator_id: str, post_id: str):
        return await self.fetch(self.path(
            "/{service}/user/{creator_id}/post/{post_id}/revisions", 
            {"service": service, "creator_id": creator_id, "post_id": post_id}),
            required_status=[200, 404],
            return_callable=lambda resp: resp.json() if resp.status == 200 else resp.text()
        )
    
    ################################ KemonoUsers ################################
    async def get_creator_profile(self, service: str, creator_id: str):
        return await self.fetch(self.path(
            "/{service}/user/{creator_id}/profile", 
            {"service": service, "creator_id": creator_id}),
            required_status=[200, 404]
        )

    async def get_creator_links_accounts(self, service: str, creator_id: str):
        return await self.fetch(self.path(
            "/{service}/user/{creator_id}/links", 
            {"service": service, "creator_id": creator_id}),
            required_status=[200, 404],
            strict=False
        )

    ################################ Comments ################################
    async def get_post_comments(self, service: str, creator_id: str, post_id: str):
        return await self.fetch(self.path(
            "/{service}/user/{creator_id}/post/{post_id}/comments", 
            {"service": service, "creator_id": creator_id, "post_id": post_id}),
            required_status=[200, 404],
            return_callable=lambda resp: resp.json() if resp.status == 200 else resp.text()
        )

    ############################### File Search ##############################
    async def hash_lookup(self, hash: str):
        return await self.fetch(self.path(
            "/search_hash/{hash}", 
            {"hash": hash})
        )
    
    ############################## Post flagging #############################
    # Flag post for re-import
    async def flag_post(self, service: str, creator_id: str, post_id: str):
        return await self.fetch(self.path(
            "/{service}/user/{creator_id}/post/{post_id}/flag", 
            {"service": service, "creator_id": creator_id, "post_id": post_id}),
            method='POST',
            required_status=[201, 409],
            return_callable=lambda resp: resp
        )
    
    async def check_post_if_flagged(self, service: str, creator_id: str, post_id: str):
        return await self.fetch(self.path(
            "/{service}/user/{creator_id}/post/{post_id}/flag", 
            {"service": service, "creator_id": creator_id, "post_id": post_id}),
            method='GET',
            required_status=[200, 404],
            return_callable=lambda resp: resp
        )
    
    ################################# Discord #################################
    async def get_discord_channel_posts(self, channel_id: str, offset: int=0, offset_=False, warning=True):
        '''offset must be a multiple of 150'''
        if offset % 150 != 0:
            raise ValueError("Offset must be a multiple of 150")
        try:
            data = await self.fetch(self.path(
                "/discord/channel/{channel_id}",
                {"channel_id": channel_id},
                {"o": offset}),
                required_status=[200, 404],
                return_callable=lambda resp: resp.json() if resp.status == 200 else resp.text(),
                warning=warning
            )
        except:
            if not offset_:
                raise
        if offset_:
            return {"data": data, "offset": offset}
        else:
            return data
        
    async def lookup_discord_channels(self, server_id: str):
        return await self.fetch(self.path(
            "/discord/channel/lookup/{server_id}",
            {"server_id": server_id}),
            required_status=[200, 404],
            return_callable=lambda resp: resp.json() if resp.status == 200 else resp.text()
        )
    
    ################################ Favorites ################################
    async def list_account_favorites(self, cookie: str=None):
        return await self.fetch(self.path(
            "/account/favorites"),
            required_status=[200, 401],
            return_callable=lambda resp: resp.json() if resp.status == 200 else resp.text(),
            cookies={"session": cookie} if cookie else None
        )
    
    async def add_favorite_post(self, service: str, creator_id: str, post_id: str, cookie: str=None):
        return await self.fetch(self.path(
            "/favorites/post/{service}/{creator_id}/{post_id}",
            {"service": service, "creator_id": creator_id, "post_id": post_id}),
            method='POST',
            required_status=[200, 302, 401],
            return_callable=lambda resp: resp.text(),
            cookies={"session": cookie} if cookie else None,
            allow_redirects=False
        )
    
    async def remove_favorite_post(self, service: str, creator_id: str, post_id: str, cookie: str=None):
        return await self.fetch(self.path(
            "/favorites/post/{service}/{creator_id}/{post_id}",
            {"service": service, "creator_id": creator_id, "post_id": post_id}),
            method='DELETE',
            required_status=[200, 302, 401],
            return_callable=lambda resp: resp.text(),
            cookies={"session": cookie} if cookie else None,
            allow_redirects=False
        )
    
    async def add_favorite_creator(self, service: str, creator_id: str, cookie: str=None):
        return await self.fetch(self.path(
            "/favorites/creator/{service}/{creator_id}",
            {"service": service, "creator_id": creator_id}),
            method='POST',
            required_status=[200, 302, 401],
            return_callable=lambda resp: resp.text(),
            cookies={"session": cookie} if cookie else None,
            allow_redirects=False
        )
    
    async def remove_favorite_creator(self, service: str, creator_id: str, cookie: str=None):
        return await self.fetch(self.path(
            "/favorites/creator/{service}/{creator_id}",
            {"service": service, "creator_id": creator_id}),
            method='DELETE',
            required_status=[200, 302, 401],
            return_callable=lambda resp: resp.text(),
            cookies={"session": cookie} if cookie else None,
            allow_redirects=False
        )
    
    #################################### File Search ####################################
    async def lookup_file_by_hash(self, hash: str):
        return await self.fetch(self.path(
            "/search_hash/{hash}",
            {"hash": hash}),
            required_status=[200, 404],
            return_callable=lambda resp: resp.json() if resp.status == 200 else resp.text()
        )
    
    async def get_app_version(self):
        '''return git commit hash'''
        return await self.fetch(self.path(
            "/app_version"),
            required_status=[200]
        )
    
    ##################################### Manual API #####################################
    async def get_creator_posts_posts_count(self, service: str, creator_id: str):
        content = await self.fetch(f"https://kemono.su/{service}/user/{creator_id}",
            return_callable=lambda resp: resp.text(),
            headers={"Referer": "https://kemono.su/artists/updated"}
        )
        if not content:
            raise KemonoAPIError("Failed to fetch creator posts count")
        soup = BeautifulSoup(content, "html.parser")
        try:
            text = soup.find("small").text.strip()
            if text.startswith("Showing"):
                count = int(text.split()[-1])
            else:
                raise
        except:
            # only one page
            items = soup.find_all(attrs={"class": "post-card post-card--preview"})
            count = len(items)
        return count
    
    async def get_archive_details(self, file_hash: str):
        content = await self.fetch("https://kemono.su/posts/archives/"+file_hash,
            return_callable=lambda resp: resp.text()
        )
        if not content:
            raise KemonoAPIError("Failed to fetch archive details")
        soup = BeautifulSoup(content, "html.parser")
        text = soup.find(attrs={"class": "main", "id": "main"}).text
        lines = [line.strip() for line in text.split("\n") if line.strip() and not line.startswith("Archive Files")]
        if lines and lines[0] == "File does not exist or is not an archive.":
            raise KemonoAPIError("File does not exist or is not an archive.")
        return lines

class KemonoCreators:
    def __init__(self, api: "KemonoAPI"):
        self.api = api
        self.creators: list[KemonoCreatorCreate] = []
        self.mapping: dict[str, int] = {}
        self._lock = asyncio.Lock()
    
    async def get_creator(self, user_hash_id: str):
        async with self._lock:
            return await self._get_creator(user_hash_id)
    
    async def _get_creator(self, user_hash_id: str):
        idx = self.mapping.get(user_hash_id)
        if idx is None:
            return None
        return self.creators[idx]
    
    async def build_creator(self, user_hash_id):
        raw_user_data = await self.api.kemono_users.get_raw_user(user_hash_id)
        link_accounts = await self.api.get_creator_links_accounts(raw_user_data.get("service"), raw_user_data.get("id"))
        await self.api.check_link_accounts_data(link_accounts)
        if self.api.kemono_users.data is None:
            await self.api.kemono_users.refresh_data()
        creator = build_kemono_creator(raw_user_data, link_accounts, self.api.kemono_users.data)
        return creator
    
    async def create_creator(self, user_hash_id):
        if user_hash_id in self.mapping:
            # need try update
            return None
        async with self._lock:
            creator = await self.build_creator(user_hash_id)
            if creator is None:
                raise KemonoAPIError(f"Failed to build creator with user {user_hash_id}")
            self.creators.append(creator)
            idx = len(self.creators) - 1
            for user_ in creator.kemono_users:
                self.mapping[user_.hash_id] = idx
            return creator
    
    async def try_update_creator(self, user_hash_id):
        async with self._lock:
            exist_creator = self.get_creator(user_hash_id)
            raise NotImplementedError()
    
    async def refresh(self):
        async with self._lock:
            await self._refresh()
    
    async def _refresh(self):
        self.mapping = {}
        self.creators = []

class KemonoUsers:
    def __init__(self, api: "KemonoAPI"):
        self.api = api
        self.data = None
        self.cache: dict[str, KemonoUser, ] = {}
        self.refresh_lock = asyncio.Lock()
        self.refresh_interval = 60*5 # 5 minutes
        self.last_refresh = None
    
    async def get_data(self):
        self.cache = {}
        data = await self.api.list_creators()
        if data is None:
            data = json_load("data/cache/creators.json")
            if data is None:
                raise KemonoAPIError("Failed to fetch creators data")
        else:
            json_dump(data, "data/cache/creators.json")
        self.data = {user_hash_id_func(d.get("id"), d.get("service")): d for d in data}
    
    async def refresh_data(self):
        self.last_refresh = asyncio.get_running_loop().time()
        await self.get_data()
        await self.api.kemono_creators._refresh()
    
    async def get_raw_user(self, user_id, service=None, refresh=False):
        async with self.refresh_lock:
            if self.data is None or refresh or self.last_refresh is None or \
                (self.last_refresh is not None and asyncio.get_running_loop().time() - self.last_refresh > self.refresh_interval):
                await self.refresh_data()
            user_hash_id = user_hash_id_func(user_id, service) if service is not None else user_id
            return self.data.get(user_hash_id)
    
    async def get_user(self, user_id, service=None, refresh=False, no_creator=False):
        async with self.refresh_lock:
            if self.data is None or refresh or self.last_refresh is None or \
                (self.last_refresh is not None and asyncio.get_running_loop().time() - self.last_refresh > self.refresh_interval):
                await self.refresh_data()
            user_hash_id = user_hash_id_func(user_id, service) if service is not None else user_id
            kemono_user = self.cache.get(user_hash_id)
            if kemono_user is None:
                kemono_user = self.data.get(user_hash_id)
                if kemono_user is None:
                    raise KemonoAPIError(f"Kemono User {user_id} not found")
                link_accounts = await self.api.get_creator_links_accounts(kemono_user.get("service"), kemono_user.get("id"))
                if link_accounts is None:
                    logger.warning(f"Failed to fetch link accounts for {user_id}")
                    link_accounts = []
                
                if creator := await self.api.kemono_creators._get_creator(user_hash_id):
                    no_creator = True
                kemono_user: KemonoUserCreate = build_kemono_user_by_kwd(no_creator=no_creator, link_accounts=link_accounts, **kemono_user)
                if no_creator and creator:
                    kemono_user.kemono_creator = creator
                self.cache[user_hash_id] = kemono_user
            return kemono_user

class Posts:
    def __init__(self, api: "KemonoAPI"):
        self.api = api
    
    async def build_all_posts(self, kemono_user: Union[KemonoUser, KemonoUserCreate], posts_info: Optional[KemonoPostsInfoCreate] = None):
        if kemono_user.service == "discord":
            posts = await self.api.get_discord_server_all_posts(kemono_user.user_id)
        else:
            posts = await self.api.get_creator_all_posts(kemono_user.service, kemono_user.user_id)
        if posts is None:
            raise KemonoAPIError("Failed to fetch posts")
        posts_info = posts_info or build_kemono_posts_info(kemono_user, len(posts))
        kemono_posts = [build_kemono_post(info=posts_info, **post) for post in posts]
        return kemono_posts

class Attachments:
    def __init__(self, api: "KemonoAPI"):
        self.api = api
    
    async def get_attachments_kwds_by_post(self, user_hash_id, post: dict) -> list[KemonoAttachmentCreate]:
        attachments = get_attachments_kwds_by_post(post)
        post_hash_id = post_hash_id_func(post.get("id"), post.get("service"))
        attachments = build_kemono_attachments(user_hash_id, post_hash_id, attachments)
        return attachments
    
    async def get_attachments_by_posts(self, user_hash_id, posts: list[dict]) -> list[KemonoAttachmentCreate]:
        attachments = []
        for post in posts:
            attachments.extend(await self.get_attachments_kwds_by_post(user_hash_id, post))
        return attachments

class KemonoAPI(BaseKemonoAPI):
    def __init__(self, api=None, session_pool: SessionPool=None):
        if api is not None:
            self.__api_url__ = api
        self.session_pool = session_pool or SessionPool()
        self.kemono_creators = KemonoCreators(self)
        self.kemono_users = KemonoUsers(self)
        self.kemono_posts = Posts(self)
        self.kemono_attachments = Attachments(self)
        self._loop = self.session_pool._loop
    
    async def get_creator_all_posts(self, service: str, creator_id: str):
        def callback(res_or_exc: Union[list[dict], Exception]):
            nonlocal c
            c += 1
            logger.info(f"Fetched {c} / {pages} pages\tfor {service}/{creator_id}")
        c = 0
        # post_legacy = await self.get_creator_posts_legacy(service, creator_id)
        post_count, posts_legacy = await asyncio.gather(self.get_creator_posts_posts_count(service, creator_id), self.get_creator_posts_legacy(service, creator_id))
        post_count_legacy = posts_legacy.get("props", {}).get("count") if posts_legacy is not None else None
        if post_count != post_count_legacy:
            if not post_count and post_count_legacy:
                post_count = post_count_legacy
            elif post_count and not post_count_legacy:
                pass
            else:
                raise KemonoAPIError(f"Post count mismatch: document count {post_count} <=> legacy api count {post_count_legacy}")
        if post_count is None:
            raise KemonoAPIInvalidResponse("Failed to fetch post count")
        pages = post_count // 50 + (post_count % 50 > 0)
        tasks = [
            self.get_creator_posts(service, creator_id, offset=i*50)
            for i in range(pages)
        ]
        tasks = pre_gather_tasks(tasks, callback=callback)
        results = await asyncio.gather(*tasks)
        posts = []
        for result in results:
            if result is None:
                raise KemonoAPIError("Failed to fetch posts")
            posts.extend(result)
        return posts
    
    async def get_discord_channel_all_posts(self, channel_id: str):
        event = asyncio.Event()
        interrupt = False
        pages = 0
        fetched_pages = 0
        end_page = None
        tasks: list[asyncio.Task] = []
        lock = asyncio.Lock()
        task_ok_map = {}
        schedule_call_map = {}

        async def fetch_page():
            nonlocal pages, interrupt, end_page
            while not interrupt:
                await asyncio.sleep(1)
                async with lock:
                    tasks.append(pre_task(
                        self.get_discord_channel_posts(channel_id, offset=pages*150, offset_=True, warning=False), 
                        callback=callback)
                    )
                    pages += 1
        
        async def callback(res_or_exc: Union[Union[list[dict], dict], Exception]):
            def schedule_call():
                nonlocal end_page
                end_page = page - 1
                event.set()
            nonlocal fetched_pages, interrupt, end_page
            async with lock:
                if event.is_set():
                    return
                data = res_or_exc.get("data")
                page = res_or_exc.get("offset") // 150
                if data:
                    fetched_pages += 1
                    logger.info(f"Fetched page {page + 1}\t{fetched_pages} / {end_page or f"?{len(tasks)}"}\t")
                if not res_or_exc or not data:
                    interrupt = True
                    # check previous page is fetched
                    pre_task_ok = task_ok_map.get(page-1)
                    if pre_task_ok:
                        end_page = page-1
                        event.set()
                    elif pre_task_ok is None:
                        # register schedule call
                        schedule_call_map[page-1] = schedule_call
                    return
                if len(data) < 150:
                    interrupt = True
                    end_page = page
                    event.set()
                else:
                    next_schedule_call = schedule_call_map.pop(page, None)
                    if next_schedule_call:
                        next_schedule_call()
                task_ok_map[page] = True
                # logger.info(f"Fetched page {page + 1}")

        async def main_task():
            nonlocal tasks, end_page, pages
            initial_tasks = [pre_task(self.get_discord_channel_posts(
                channel_id, offset=i*150, offset_=True, warning=False),
                callback=callback
                ) for i in range(3)]
            tasks.extend(initial_tasks)
            pages += len(initial_tasks)
            try:
                await asyncio.wait_for(event.wait(), timeout=settings.kemono_api.get_discord_channel_all_posts_timeout)
            except asyncio.TimeoutError:
                pass
            if end_page is None:
                raise KemonoAPIError("Timeout error: Failed to fetch posts")

            # Cancel extra tasks after end_page
            for task in tasks[end_page+1:]:
                task.cancel()

        await asyncio.gather(fetch_page(), main_task())

        # Collect results
        posts = []
        results = await asyncio.gather(*tasks[:end_page+1], return_exceptions=True)
        for result in results:
            if isinstance(result, Exception) or result.get("data") is None:
                raise KemonoAPIError("Failed to fetch posts")
            posts.extend(result.get("data"))

        return posts
    
    async def get_discord_server_all_posts(self, server_id: str):
        channels = await self.lookup_discord_channels(server_id)
        if channels is None:
            raise KemonoAPIError("Failed to fetch channels")
        all_posts = []
        for channel in channels:
            channel_id = channel.get("id")
            channel_name = channel.get("name")
            logger.info(f"Fetching posts from {channel_name} ({channel_id})")
            try:
                posts = await self.get_discord_channel_all_posts(channel_id)
            except KemonoAPIError as e:
                logger.warning(f"Failed to fetch posts from {channel_name} ({channel_id}): {e}")
                continue
            all_posts.extend(posts)
        return all_posts
    
    async def check_link_accounts_data(self, data: list[dict]):
        for i in range(len(data) -1, -1, -1):
            hash_id = user_hash_id_func(data[i].get("id"), data[i].get("service"))
            if not self.kemono_users.data:
                await self.kemono_users.refresh_data()
            if hash_id not in self.kemono_users.data:
                logger.warning(f"Link account {hash_id} not found in users data, remove it.")
                data.pop(i)
