import asyncio
from concurrent.futures import Future
from yarl import URL
from re import sub
from bs4 import BeautifulSoup

from rich import print
from typing import Optional, Awaitable, Callable, TypeVar, Union, Any

from aiohttp import ClientResponse
from kemonobakend.database.models import (
    KemonoCreatorCreate, KemonoUser, KemonoUserCreate, 
    KemonoPostsInfoCreate,
    KemonoAttachmentCreate)
from kemonobakend.database.model_builder import (
    build_kemono_user_by_kwd, build_kemono_creator,
    build_kemono_post,  build_kemono_posts_info,
    get_attachments_kwds_by_post, build_kemono_attachments
)
from kemonobakend.kemono.builtins import (
    get_service_site, user_hash_id_func, post_hash_id_func, get_user_id_service_by_hash_id,
    ALL_SERVICES, KEMONO_API_URL, COOMER_API_URL)
from kemonobakend.session_pool import SessionPool
from kemonobakend.utils import json_load, json_dump, json_loads
from kemonobakend.utils.aiotools import pre_gather_tasks, pre_task
from kemonobakend.log import logger
from kemonobakend.config import settings

from .base import BaseAPI, NotFoundError, PartySuAPIError, PartySuAPIInvalidResponse



class RespSolutionFuncs:
    
    @staticmethod
    async def _get_error(resp: ClientResponse, err_default: str = "Not Found"):
        try:
            err = await resp.text()
            try:
                err = json_load(err)
                err = err.get('error', err_default)
            except:
                if not isinstance(err, str):
                    err = err_default
        except:
            err = err_default
        return err
    
    @classmethod
    def json_resp_2(cls, err_default: str = "Not Found", strict: bool = False):
        '''
        JSON response with 200 status code
        with one anther status code
        '''
        async def _wrapper(resp: ClientResponse):
            if resp.status == 200:
                ret = await resp.json()
                if strict and not ret:
                    raise PartySuAPIInvalidResponse("Empty response")
                return ret
            else:
                err = await cls._get_error(resp, err_default)
                raise NotFoundError(err)
        return _wrapper
    
    @classmethod
    def text2json_resp_2(cls, err_default: str = "Not Found"):
        '''
        JSON response with 200 status code
        with one anther status code
        '''
        async def _wrapper(resp: ClientResponse):
            if resp.status == 200:
                text = await resp.text()
                return json_loads(text)
            else:
                err = await cls._get_error(resp, err_default)
                raise NotFoundError(err)
        return _wrapper
    
    @classmethod
    def text_resp(cls):
        async def _wrapper(resp: ClientResponse):
            return await resp.text()
        return _wrapper
    
    @classmethod
    def text_resp_s(cls, type: Optional[str] = None):
        async def _wrapper(resp: ClientResponse):
            data = await resp.text()
            if type != 'text':
                try:
                    data = json_load(data)
                except:
                    data = data
            return resp.status, data
        return _wrapper
    
    @classmethod
    def post_resp_s(cls, type: Optional[str] = None):
        async def _wrapper(resp: ClientResponse):
            data = await resp.text()
            if type != 'text':
                try:
                    data = json_load(data)
                except:
                    pass
            return resp.status, data
        return _wrapper



class BasePartySuAPI(BaseAPI):
    __services__ = ALL_SERVICES
    __api_url_map__ = {
        "kemono": KEMONO_API_URL,
        "coomer": COOMER_API_URL
    }
    
    ################################# Posts #################################
    async def list_creators(self, site_or_service: str) -> list:
        '''
        `Status: 200 OK`
        TEXT or JSON response
        ```json
        [
            {
                "favorited": 1,
                "id": "21101760",
                "indexed": 1672534800,
                "name": "RAIGYO",
                "service": "fanbox",
                "updated": 1672534800
            }
        ]
        ```
        '''
        url = self.path('/creators.txt', site_or_service)
        return await self.fetch(url, RespSolutionFuncs.text2json_resp_2("Creator not found"), required_status=[200, 404])
    
    async def list_recent_posts(self, site_or_service: str, offset: int=0, search_query: str=None, tag: Union[str, list[str]]=None):
        '''
        `Status: 200 OK`
        ```json
        [
            {
                "id": "1836570",
                "user": "6570768",
                "service": "fanbox",
                "title": "今日はFANBOXを始まりました！",
                "content": "<p>みなさんこんにちは、影おじです。</p><p>先週のように、FANBOXを始まりに決定しました！</p><p>そしてFANBOXの更新内容について、アンケートのみなさん</p><p>ありがとうございました！</p><p><br/></p><p>では更新内容の詳しいことはこちらです↓</p><p>毎回の絵、元も差分がありませんの場合、ボナスとして差分イラストを支援者の皆様にプレゼント。</p><p>もとも差分があれば、ボナスとしてヌード差分イラストを支援者の皆様にプレゼント。</p><p><br/></p><p>これから、仕事以外の時間、できる限り勤勉な更新したいと思います！</p><p>どうぞよろしくお願いいたします！</p>",
                "embed": {},
                "shared_file": false,
                "added": "2021-03-30T18:00:05.973913",
                "published": "2021-01-24T17:54:38",
                "edited": "2021-01-24T18:46:15",
                "file": {
                    "name": "a99d9674-5490-400e-acca-4bed99590699.jpg",
                    "path": "/5c/98/5c984d1f62f0990a0891d8fa359aecdff6ac1e26ac165ba7bb7f31cc99e7a674.jpg"
                },
                "attachments": []
            },
            {
                "id": "1836649",
                "user": "6570768",
                "service": "fanbox",
                "title": "忍ちゃん  脇コキ差分",
                "content": "",
                "embed": {},
                "shared_file": false,
                "added": "2021-03-30T17:59:57.815397",
                "published": "2021-01-24T18:23:12",
                "edited": "2023-01-04T14:45:19",
                "file": {
                    "name": "4c5615f9-be74-4fa7-b88d-168fd37a2824.jpg",
                    "path": "/d0/3c/d03c893927521536646619f5fb33426aa4b82dc12869865d6d666932755d9acd.jpg"
                },
                "attachments": [
                    {
                        "name": "9cc982e4-1d94-4a1a-ac62-3dddd29f881c.png",
                        "path": "/d7/4d/d74d1727f2c3fcf7a7cc2d244d677d93b4cc562a56904765e4e708523b34fb4c.png"
                    },
                    {
                        "name": "ab0e17d7-52e5-42c2-925b-5cfdb451df0c.png",
                        "path": "/1b/67/1b677a8c0525e386bf2b2f013e36e29e4033feb2308798e4e5e3780da6c0e815.png"
                    }
                ]
            }
        ]
        ```
        '''
        if offset % 50 != 0:
            raise ValueError("Offset must be a multiple of 50")
        if tag is not None and not isinstance(tag, str):
            tag = ','.join(tag)
        url = self.path('/posts', site_or_service, query={"o": offset, "q": search_query, "t": tag})
        return await self.fetch(url)

    async def get_creator_posts(self, service: str, creator_id: str, offset: int=0, search_query: str=None) -> Optional[Union[list[dict], dict]]:
        '''
        `Status: 200 OK`
        ```json
        [
            {
                "id": "1836570",
                "user": "6570768",
                "service": "fanbox",
                "title": "今日はFANBOXを始まりました！",
                "content": "<p>みなさんこんにちは、影おじです。</p><p>先週のように、FANBOXを始まりに決定しました！</p><p>そしてFANBOXの更新内容について、アンケートのみなさん</p><p>ありがとうございました！</p><p><br/></p><p>では更新内容の詳しいことはこちらです↓</p><p>毎回の絵、元も差分がありませんの場合、ボナスとして差分イラストを支援者の皆様にプレゼント。</p><p>もとも差分があれば、ボナスとしてヌード差分イラストを支援者の皆様にプレゼント。</p><p><br/></p><p>これから、仕事以外の時間、できる限り勤勉な更新したいと思います！</p><p>どうぞよろしくお願いいたします！</p>",
                "embed": {},
                "shared_file": false,
                "added": "2021-03-30T18:00:05.973913",
                "published": "2021-01-24T17:54:38",
                "edited": "2021-01-24T18:46:15",
                "file": {
                    "name": "a99d9674-5490-400e-acca-4bed99590699.jpg",
                    "path": "/5c/98/5c984d1f62f0990a0891d8fa359aecdff6ac1e26ac165ba7bb7f31cc99e7a674.jpg"
                },
                "attachments": []
            },
            {
                "id": "1836649",
                "user": "6570768",
                "service": "fanbox",
                "title": "忍ちゃん  脇コキ差分",
                "content": "",
                "embed": {},
                "shared_file": false,
                "added": "2021-03-30T17:59:57.815397",
                "published": "2021-01-24T18:23:12",
                "edited": "2023-01-04T14:45:19",
                "file": {
                    "name": "4c5615f9-be74-4fa7-b88d-168fd37a2824.jpg",
                    "path": "/d0/3c/d03c893927521536646619f5fb33426aa4b82dc12869865d6d666932755d9acd.jpg"
                },
                "attachments": [
                    {
                        "name": "9cc982e4-1d94-4a1a-ac62-3dddd29f881c.png",
                        "path": "/d7/4d/d74d1727f2c3fcf7a7cc2d244d677d93b4cc562a56904765e4e708523b34fb4c.png"
                    },
                    {
                        "name": "ab0e17d7-52e5-42c2-925b-5cfdb451df0c.png",
                        "path": "/1b/67/1b677a8c0525e386bf2b2f013e36e29e4033feb2308798e4e5e3780da6c0e815.png"
                    }
                ]
            }
        ]
        ```
        `Status: 400 Bad Request`
        ```text
        Offset provided which is not a multiple of 50
        ```
        `Status: 404 Not Found`
        ```json
        {
            "error": "Creator not found."
        }
        ```
        '''
        if offset % 50 != 0:
            raise ValueError("Offset must be a multiple of 50")
        
        url = self.path(
            "/{service}/user/{creator_id}", service,
            format={"service": service, "creator_id": creator_id},
            query={"o": offset, "q": search_query}
        )
        return await self.fetch(url, RespSolutionFuncs.json_resp_2("Creator not found", strict=True), required_status=[200, 404])
    
    async def get_creator_posts_legacy(self, service: str, creator_id: str, offset: int=0, search_query: str=None):
        '''
        `Status: 200 OK`
        ```json
        {
            "props": {
                "currentPage": "posts",
                "id": "string",
                "service": "string",
                "name": "string",
                "count": 0,
                "limit": 0,
                "artist": {
                    "id": "string",
                    "name": "string",
                    "service": "string",
                    "indexed": "string",
                    "updated": "string",
                    "public_id": "string",
                    "relation_id": 0
                },
                "display_data": {
                    "service": "string",
                    "href": "string"
                },
                "dm_count": 0,
                "share_count": 0,
                "has_links": "string"
            },
            "base": {},
            "results": [
                {
                    "id": "string",
                    "user": "string",
                    "service": "string",
                    "title": "string",
                    "content": "string",
                    "embed": {},
                    "shared_file": true,
                    "added": "string",
                    "published": "string",
                    "edited": "string",
                    "file": {},
                    "attachments": [
                        {}
                    ]
                }
            ],
            "result_previews": [
                {}
            ],
            "result_attachments": [
                {}
            ],
            "result_is_image": [
                true
            ],
            "disable_service_icons": true
        }
        ```
        '''
        if offset % 50 != 0:
            raise ValueError("Offset must be a multiple of 50")
        
        url = self.path(
            "/{service}/user/{creator_id}/posts-legacy", service,
            format={"service": service, "creator_id": creator_id},
            query={"o": offset, "q": search_query}
        )
        return await self.fetch(url)

    async def get_creator_announcements(self, service: str, creator_id: str):
        '''
        `Status: 200 OK`
        ```json
        [
            {
                "service": "patreon",
                "user_id": "8693043",
                "hash": "820b7397c7f75efb13c4a8aa5d4aacfbb200749f3e1cec16e9f2951d158be8c2",
                "content": "Hey guys, thank you so much for your support, that means a lot to me!",
                "added": "2023-01-31T05:16:15.462035"
            }
        ]
        ```
        `Status: 404 Not Found`
        ```text
        Artist not found
        ```
        '''
        url = self.path(
            "/{service}/user/{creator_id}/announcements", service,
            format={"service": service, "creator_id": creator_id}
        )
        return await self.fetch(url, RespSolutionFuncs.json_resp_2("Artist not found"), required_status=[200, 404])

    async def get_creator_fancards(self, service: str, creator_id: str):
        '''
        `Status: 200 OK`
        ```json
        [
            {
                "id": 108058645,
                "user_id": "3316400",
                "file_id": 108058645,
                "hash": "727bf3f0d774a98c80cf6c76c3fb0e049522b88eb7f02c8d3fc59bae20439fcf",
                "mtime": "2023-05-23T15:09:43.941195",
                "ctime": "2023-05-23T15:09:43.941195",
                "mime": "image/jpeg",
                "ext": ".jpg",
                "added": "2023-05-23T15:09:43.960578",
                "size": 339710,
                "ihash": null
            },
            {
                "id": 103286760,
                "user_id": "3316400",
                "file_id": 103286760,
                "hash": "8b0d0f1be38efab9306b32c7b14b74ddd92a2513026c859a280fe737980a467d",
                "mtime": "2023-04-26T14:16:53.205183",
                "ctime": "2023-04-26T14:16:53.205183",
                "mime": "image/jpeg",
                "ext": ".jpg",
                "added": "2023-04-26T14:16:53.289143",
                "size": 339764,
                "ihash": null
            }
        ]
        ```
        `Status: 404 Not Found`
        ```text
        Artist not found
        ```
        '''
        if service != "fanbox":
            raise ValueError("Fancards are only available for Fanbox")
        url = self.path(
            "/{service}/user/{creator_id}/fancards", "kemono",
            format={"service": service, "creator_id": creator_id}
        )
        return await self.fetch(url, RespSolutionFuncs.json_resp_2("Artist not found"), required_status=[200, 404],)

    async def get_specific_post(self, service: str, creator_id: str, post_id: str):
        '''
        `Status: 200 OK`
        ```json
        {
            "post": {
                "id": "1836570",
                "user": "6570768",
                "service": "fanbox",
                "title": "今日はFANBOXを始まりました！",
                "content": "<p>みなさんこんにちは、影おじです。</p><p>先週のように、FANBOXを始まりに決定しました！</p><p>そしてFANBOXの更新内容について、アンケートのみなさん</p><p>ありがとうございました！</p><p><br/></p><p>では更新内容の詳しいことはこちらです↓</p><p>毎回の絵、元も差分がありませんの場合、ボナスとして差分イラストを支援者の皆様にプレゼント。</p><p>もとも差分があれば、ボナスとしてヌード差分イラストを支援者の皆様にプレゼント。</p><p><br/></p><p>これから、仕事以外の時間、できる限り勤勉な更新したいと思います！</p><p>どうぞよろしくお願いいたします！</p>",
                "embed": {},
                "shared_file": false,
                "added": "2021-03-30T18:00:05.973913",
                "published": "2021-01-24T17:54:38",
                "edited": "2021-01-24T18:46:15",
                "file": {
                    "name": "a99d9674-5490-400e-acca-4bed99590699.jpg",
                    "path": "/5c/98/5c984d1f62f0990a0891d8fa359aecdff6ac1e26ac165ba7bb7f31cc99e7a674.jpg"
                },
                "attachments": [],
                "next": null,
                "prev": "1836649"
            }
        }
        ```
        `Status: 404 Not Found`
        ```text
        Post not found
        ```
        '''
        url = self.path(
            "/{service}/user/{creator_id}/post/{post_id}", service,
            format={"service": service, "creator_id": creator_id, "post_id": post_id}
        )
        return await self.fetch(url, RespSolutionFuncs.json_resp_2("Post not found"), required_status=[200, 404])

    async def list_posts_revisions(self, service: str, creator_id: str, post_id: str):
        '''
        `Status: 200 OK`
        ```json
        [
            {
                "revision_id": 8059287,
                "id": "1836570",
                "user": "6570768",
                "service": "fanbox",
                "title": "今日はFANBOXを始まりました！",
                "content": "<p>みなさんこんにちは、影おじです。</p><p>先週のように、FANBOXを始まりに決定しました！</p><p>そしてFANBOXの更新内容について、アンケートのみなさん</p><p>ありがとうございました！</p><p><br/></p><p>では更新内容の詳しいことはこちらです↓</p><p>毎回の絵、元も差分がありませんの場合、ボナスとして差分イラストを支援者の皆様にプレゼント。</p><p>もとも差分があれば、ボナスとしてヌード差分イラストを支援者の皆様にプレゼント。</p><p><br/></p><p>これから、仕事以外の時間、できる限り勤勉な更新したいと思います！</p><p>どうぞよろしくお願いいたします！</p>",
                "embed": {},
                "shared_file": false,
                "added": "2023-09-19T13:19:57.416086",
                "published": "2021-01-24T17:54:38",
                "edited": "2021-01-24T18:46:15",
                "file": {
                    "name": "8c2be0fd-a130-4afb-9314-80f2501d94f7.jpg",
                    "path": "/5c/98/5c984d1f62f0990a0891d8fa359aecdff6ac1e26ac165ba7bb7f31cc99e7a674.jpg"
                },
                "attachments": [
                    {
                        "name": "attachment1.jpg",
                        "path": "/attachments/attachment1.jpg"
                    },
                    {
                        "name": "attachment2.jpg",
                        "path": "/attachments/attachment2.jpg"
                    }
                ]
            },
            {
                "revision_id": 6770513,
                "id": "1836570",
                "user": "6570768",
                "service": "fanbox",
                "title": "今日はFANBOXを始まりました！",
                "content": "<p>みなさんこんにちは、影おじです。</p><p>先週のように、FANBOXを始まりに決定しました！</p><p>そしてFANBOXの更新内容について、アンケートのみなさん</p><p>ありがとうございました！</p><p><br/></p><p>では更新内容の詳しいことはこちらです↓</p><p>毎回の絵、元も差分がありませんの場合、ボナスとして差分イラストを支援者の皆様にプレゼント。</p><p>もとも差分があれば、ボナスとしてヌード差分イラストを支援者の皆様にプレゼント。</p><p><br/></p><p>これから、仕事以外の時間、できる限り勤勉な更新したいと思います！</p><p>どうぞよろしくお願いいたします！</p>",
                "embed": {},
                "shared_file": false,
                "added": "2023-07-28T23:51:25.477291",
                "published": "2021-01-24T17:54:38",
                "edited": "2021-01-24T18:46:15",
                "file": {
                    "name": "0d133e49-a2d4-4733-9044-dd57e25b1fce.jpg",
                    "path": "/5c/98/5c984d1f62f0990a0891d8fa359aecdff6ac1e26ac165ba7bb7f31cc99e7a674.jpg"
                },
                "attachments": [
                    {
                        "name": "attachment3.jpg",
                        "path": "/attachments/attachment3.jpg"
                    },
                    {
                        "name": "attachment4.jpg",
                        "path": "/attachments/attachment4.jpg"
                    }
                ]
            }
        ]
        ```
        `Status: 404 Not Found`
        ```text
        Post not found
        ```
        '''
        url = self.path(
            "/{service}/user/{creator_id}/post/{post_id}/revisions", service,
            format={"service": service, "creator_id": creator_id, "post_id": post_id}
        )
        return await self.fetch(url, RespSolutionFuncs.json_resp_2("Post not found"), required_status=[200, 404])
    
    ################################ KemonoUsers ################################
    async def get_creator_profile(self, service: str, creator_id: str):
        '''
        `Status: 200 OK`
        ```json
        {
            "id": "string",
            "public_id": "string",
            "service": "string",
            "name": "string",
            "indexed": "2024-11-30T03:20:06.551Z",
            "updated": "2024-11-30T03:20:06.551Z"
        }
        ```
        `Status: 404 Not Found`
        ```json
        {
            "error": "Creator not found."
        }
        ```
        '''
        url = self.path(
            "/{service}/user/{creator_id}/profile", service,
            format={"service": service, "creator_id": creator_id}
        )
        return await self.fetch(url, RespSolutionFuncs.json_resp_2("Creator not found"), required_status=[200, 404])

    async def get_creator_links_accounts(self, service: str, creator_id: str):
        '''
        `Status: 200 OK`
        ```json
        [
            {
                "id": "string",
                "public_id": "string",
                "service": "string",
                "name": "string",
                "indexed": "2024-11-30T03:23:07.049Z",
                "updated": "2024-11-30T03:23:07.049Z"
            }
        ]
        ```
        `Status: 404 Not Found`
        ```json
        {
            "error": "Creator not found."
        }
        ```
        '''
        url = self.path(
            "/{service}/user/{creator_id}/links", service,
            format={"service": service, "creator_id": creator_id}
        )
        return await self.fetch(url, RespSolutionFuncs.json_resp_2("Creator not found"), required_status=[200, 404])
    
    async def get_creator_tags(self, service: str, creator_id: str):
        '''
        `Status: 200 OK`
        ```json
        {
            "props": "string",
            "tags": [
                {
                    "tag": "string",
                    "post_count": 0
                }
            ],
            "service": "string",
            "artist": {
                "id": "string",
                "name": "string",
                "service": "string",
                "indexed": "string",
                "updated": "string",
                "public_id": "string",
                "relation_id": 0
            }
        }
        ```
        '''
        url = self.path(
            "/{service}/user/{creator_id}/tags", service,
            format={"service": service, "creator_id": creator_id}
        )
        return await self.fetch(url)

    ################################ Comments ################################
    async def get_post_comments(self, service: str, creator_id: str, post_id: str):
        '''
        `Status: 200 OK`
        ```json
        [
            {
                "id": "121508687",
                "parent_id": null,
                "commenter": "84534108",
                "content": "YOU DREW MORE YAYYYY",
                "published": "2023-11-05T20:17:47.635000",
                "revisions": [
                    {
                        "id": 1,
                        "content": "YOU DREW MORE YAYYYY2222222",
                        "added": "2023-11-14T03:09:12.275975"
                    }
                ]
            }
        ]
        ```
        `Status: 404 Not Found`
        ```text
        No comments found.
        ```
        '''
        url = self.path(
            "/{service}/user/{creator_id}/post/{post_id}/comments", service,
            format={"service": service, "creator_id": creator_id, "post_id": post_id}
        )
        return await self.fetch(url, RespSolutionFuncs.json_resp_2("No comments found."), required_status=[200, 404])

    ############################## Post flagging #############################
    # Flag post for re-import
    async def flag_post(self, service: str, creator_id: str, post_id: str):
        '''
        `return`
        ```json
        {
            "status": "int | None",
            "msg": "str",
        }
        ```
        `Status: 201 Created`
        ```json
        true
        ```
        `Status: 409 Conflict`
        ```json
        true
        ```
        '''
        url = self.path(
            "/{service}/user/{creator_id}/post/{post_id}/flag", service,
            {"service": service, "creator_id": creator_id, "post_id": post_id}
        )
        ret = await self.fetch(
            url,
            RespSolutionFuncs.post_resp_s(),
            method='POST',
            required_status=[201, 409],
        )
        if ret is None:
            return {"status": None, "msg": "Network error"}
        return {"status": ret[0] == 201, "msg": ret[1]}
    
    async def check_post_if_flagged(self, service: str, creator_id: str, post_id: str):
        '''
        `Return`
        ```json
        {
            "success": "bool",
            "msg": "str",
            "status": "int | None"
        }
        ```
        `Status: 200 OK`
        ```text
        The post is flagged
        ```
        `Status: 404 Not Found`
        ```text
        The post has no flag
        ```
        '''
        url = self.path(
            "/{service}/user/{creator_id}/post/{post_id}/flag", service,
            format={"service": service, "creator_id": creator_id, "post_id": post_id}
        )
        ret = await self.fetch(
            url,
            RespSolutionFuncs.text_resp_s(),
            required_status=[200, 404],
        )
        if ret is None:
            return {"success": False, "msg": "Network error", "status": None}
        elif ret[0] == 200:
            return {"success": True, "msg": ret[1], "status": ret[0]}
        elif ret[0] == 404:
            return {"success": False, "msg": ret[1], "status": ret[0]}
        else:
            return {"success": False, "msg": "Unknown error", "status": ret[0]}
    
    ################################# Discord #################################
    async def get_discord_channel_posts(self, channel_id: str, offset: int=0, offset_=False, warning=True):
        '''
        `Status: 200 OK`
        ```json
        [
            {
                "id": "942909658610413578",
                "author": {
                    "id": "421590382300889088",
                    "avatar": "0956f3dc18eba7da9daedc4e50fb96d0",
                    "username": "Merry",
                    "public_flags": 0,
                    "discriminator": "7849"
                },
                "server": "455285536341491714",
                "channel": "455287420959850496",
                "content": "@everyone Happy Valentine’s Day! 💜✨",
                "added": "2022-02-15T01:26:12.708959",
                "published": "2022-02-14T22:26:21.027000",
                "edited": null,
                "embeds": [],
                "mentions": [],
                "attachments": []
            },
            {
                "id": "942909571947712594",
                "author": {
                    "id": "421590382300889088",
                    "avatar": "0956f3dc18eba7da9daedc4e50fb96d0",
                    "username": "Merry",
                    "public_flags": 0,
                    "discriminator": "7849"
                },
                "server": "455285536341491714",
                "channel": "455287420959850496",
                "content": "",
                "added": "2022-02-15T01:26:13.006228",
                "published": "2022-02-14T22:26:00.365000",
                "edited": null,
                "embeds": [],
                "mentions": [],
                "attachments": [
                    {
                        "name": "sofa_03.png",
                        "path": "/3b/4e/3b4ed5aabdd85b26fbbc3ee9b0e5649df69167efe26b5abc24cc2a1159f446d4.png"
                    }
                ]
            }
        ]
        ```
        `Status: 404 Not Found`
        ```text
        Discord channel not found
        ```
        '''
        if offset % 150 != 0:
            raise ValueError("Offset must be a multiple of 150")
        url = self.path(
            "/discord/channel/{channel_id}", site_or_service="kemono",
            format={"channel_id": channel_id},
            query={"o": offset}
        )
        try:
            data = await self.fetch(
                url,
                RespSolutionFuncs.json_resp_2("Discord channel not found"),
                required_status=[200, 404],
                warning=warning,
            )
        except:
            if not offset_:
                raise
        if offset_:
            return {"data": data, "offset": offset}
        else:
            return data
        
    async def lookup_discord_channels(self, server_id: str):
        '''
        `Status: 200 OK`
        ```json
        [
            {
                "id": "455285536341491716",
                "name": "news"
            },
            {
                "id": "455287420959850496",
                "name": "nyarla-lewds"
            }
        ]
        ```
        `Status: 404 Not Found`
        ```text
        Discord server not found
        ```
        '''
        url = self.path(
            "/discord/channel/lookup/{server_id}", "kemono",
            format={"server_id": server_id}
        )
        return await self.fetch(
            url,
            RespSolutionFuncs.json_resp_2("Discord server not found"),
            required_status=[200, 404],
        )
    
    ################################ Favorites ################################
    async def list_account_favorites(self, site_or_service: str, cookie: Optional[Union[str, Any]]=None):
        '''
        `Status: 200 OK`
        ```json
        [
            {
                "faved_seq": 0,
                "id": "string",
                "indexed": "string",
                "last_imported": "string",
                "name": "string",
                "service": "string",
                "updated": "string"
            }
        ]
        ```
        `Status: 401 Unauthorized`
        ```text
        Unauthorized Access
        ```
        '''
        if isinstance(cookie, str):
            cookie = {"session": cookie}
        url = self.path("/account/favorites", site_or_service)
        return await self.fetch(
            url,
            RespSolutionFuncs.json_resp_2("Unauthorized Access"),
            required_status=[200, 401],
            cookies=cookie
        )
    
    async def add_favorite_post(self, service: str, creator_id: str, post_id: str, cookie: Optional[Union[str, Any]]=None):
        '''
        `Return`
        ```json
        {
            "success": "bool",
            "msg": "str",
            "status": "int | None"
        }
        `Status: 200 OK`
        ```text
        Favorite post added successfully
        ```
        `Status: 302 Redirect`
        ```text
        Redirect to login if not authenticated
        ```
        `Status: 401 Unauthorized`
        ```text
        Unauthorized Access
        ```
        '''
        if isinstance(cookie, str):
            cookie = {"session": cookie}
        url = self.path(
            "/favorites/post/{service}/{creator_id}/{post_id}", service,
            format={"service": service, "creator_id": creator_id, "post_id": post_id}
        )
        ret = await self.fetch(
            url,
            RespSolutionFuncs.post_resp_s("text"),
            method='POST',
            required_status=[200, 302, 401],
            cookies=cookie,
            allow_redirects=False
        )
        if ret is None:
            return {"success": False, "msg": "Network error", "status": None}
        elif ret[0] == 200:
            return {"success": True, "msg": ret[1], "status": ret[0]}
        elif ret[0] in [302, 401]:
            return {"success": False, "msg": ret[1], "status": ret[0]}
        else:
            return {"success": False, "msg": "Unknown error", "status": ret[0]}
    
    async def remove_favorite_post(self, service: str, creator_id: str, post_id: str, cookie: str=None):
        '''
        `Return`
        ```json
        {
            "success": "bool",
            "msg": "str",
            "status": "int | None"
        }
        `Status: 200 OK`
        ```text
        Unfavorite post removed successfully
        ```
        `Status: 302 Redirect`
        ```text
        Redirect to login if not authenticated
        ```
        `Status: 401 Unauthorized`
        ```text
        Unauthorized Access
        ```
        '''
        if isinstance(cookie, str):
            cookie = {"session": cookie}
        url = self.path(
            "/favorites/post/{service}/{creator_id}/{post_id}", service,
            format={"service": service, "creator_id": creator_id, "post_id": post_id}
        )
        ret = await self.fetch(
            url,
            RespSolutionFuncs.post_resp_s("text"),
            method='DELETE',
            required_status=[200, 302, 401],
            cookies=cookie,
            allow_redirects=False
        )
        if ret is None:
            return {"success": False, "msg": "Network error", "status": None}
        elif ret[0] == 200:
            return {"success": True, "msg": ret[1], "status": ret[0]}
        elif ret[0] in [302, 401]:
            return {"success": False, "msg": ret[1], "status": ret[0]}
        else:
            return {"success": False, "msg": "Unknown error", "status": ret[0]}
    
    async def add_favorite_creator(self, service: str, creator_id: str, cookie: str=None):
        '''
        `Return`
        ```json
        {
            "success": "bool",
            "msg": "str",
            "status": "int | None"
        }
        `Status: 200 OK`
        ```text
        Favorite creator added successfully
        ```
        `Status: 302 Redirect`
        ```text
        Redirect to login if not authenticated
        ```
        `Status: 401 Unauthorized`
        ```text
        Unauthorized Access
        ```
        '''
        if isinstance(cookie, str):
            cookie = {"session": cookie}
        url = self.path(
            "/favorites/creator/{service}/{creator_id}", service,
            format={"service": service, "creator_id": creator_id}
        )
        ret = await self.fetch(
            url,
            RespSolutionFuncs.post_resp_s("text"),
            method='POST',
            required_status=[200, 302, 401],
            cookies=cookie,
            allow_redirects=False
        )
        if ret is None:
            return {"success": False, "msg": "Network error", "status": None}
        elif ret[0] == 200:
            return {"success": True, "msg": ret[1], "status": ret[0]}
        elif ret[0] in [302, 401]:
            return {"success": False, "msg": ret[1], "status": ret[0]}
        else:
            return {"success": False, "msg": "Unknown error", "status": ret[0]}
    
    async def remove_favorite_creator(self, service: str, creator_id: str, cookie: str=None):
        '''
        `Return`
        ```json
        {
            "success": "bool",
            "msg": "str",
            "status": "int | None"
        }
        `Status: 200 OK`
        ```text
        Unfavorite creator removed successfully
        ```
        `Status: 302 Redirect`
        ```text
        Redirect to login if not authenticated
        ```
        `Status: 401 Unauthorized`
        ```text
        Unauthorized Access
        ```
        '''
        if isinstance(cookie, str):
            cookie = {"session": cookie}
        url = self.path(
            "/favorites/creator/{service}/{creator_id}", service,
            format={"service": service, "creator_id": creator_id}
        )
        ret = await self.fetch(
            url,
            RespSolutionFuncs.post_resp_s("text"),
            method='DELETE',
            required_status=[200, 302, 401],
            cookies=cookie,
            allow_redirects=False
        )
        if ret is None:
            return {"success": False, "msg": "Network error", "status": None}
        elif ret[0] == 200:
            return {"success": True, "msg": ret[1], "status": ret[0]}
        elif ret[0] in [302, 401]:
            return {"success": False, "msg": ret[1], "status": ret[0]}
        else:
            return {"success": False, "msg": "Unknown error", "status": ret[0]}
    
    #################################### File Search ####################################
    async def lookup_file_by_hash(self, site_or_service: str, hash: str):
        '''
        `Status: 200 OK`
        ```json
        {
            "id": 40694581,
            "hash": "b926020cf035af45a1351e0a7e2c983ebcc93b4c751998321a6593a98277cdeb",
            "mtime": "2021-12-04T07:16:09.385539",
            "ctime": "2021-12-04T07:16:09.385539",
            "mime": "image/png",
            "ext": ".png",
            "added": "2021-12-04T07:16:09.443016",
            "size": 10869921,
            "ihash": null,
            "posts": [
                {
                    "file_id": 108400151,
                    "id": "5956097",
                    "user": "21101760",
                    "service": "fanbox",
                    "title": "Loli Bae",
                    "substring": "Thank you for your continued support!\nいつも支援ありがとうご",
                    "published": "2023-05-14T00:00:00",
                    "file": {
                        "name": "8f183dac-470d-4587-9657-23efe8890a7b.jpg",
                        "path": "/e5/1f/e51fc831dfdac7a21cc650ad46af59340e35e2a051aed8c1e65633592f4dc11c.jpg"
                    },
                    "attachments": [
                        {
                            "name": "b644eb9c-cffa-400e-9bd6-40cccb2331ba.png",
                            "path": "/5e/b3/5eb3197668ac23bd7c473d3c750334eb206b060c610e4ac5fa1a9370fd1314d9.png"
                        },
                        {
                            "name": "17f295ba-a9f2-4034-aafc-bf74904ec144.png",
                            "path": "/88/ad/88ad2ba77c89e4d7a9dbe1f9531ba3e3077a82aee2b61efa29fda122ebe1b516.png"
                        }
                    ]
                }
            ],
            "discord_posts": [
                {
                    "file_id": 40694581,
                    "id": "769704201495904286",
                    "server": "455285536341491714",
                    "channel": "769703874356445216",
                    "substring": "",
                    "published": "2020-10-24T23:29:42.049",
                    "embeds": [],
                    "mentions": [],
                    "attachments": [
                        {
                            "name": "3.png",
                            "path": "/b9/26/b926020cf035af45a1351e0a7e2c983ebcc93b4c751998321a6593a98277cdeb.png"
                        }
                    ]
                }
            ]
        }
        ```
        `Status: 404 Not Found`
        ```text
        File not found
        ```
        '''
        url = self.path(
            "/search_hash/{hash}", site_or_service,
            format={"hash": hash})
        return await self.fetch(url, RespSolutionFuncs.json_resp_2("File not found"), required_status=[200, 404])
    
    async def get_app_version(self, site_or_service: str):
        url = self.path("/app_version", site_or_service)
        return await self.fetch(
            url,
            RespSolutionFuncs.text_resp(),
        )
    
    #################################### Default API #####################################
    async def get_random_post(self, site_or_service: str):
        '''
        `Status: 200 OK`
        ```json
        {
            "service": "string",
            "artist_id": "string",
            "post_id": "string"
        }
        ```
        `Status: 404 Not Found`
        ```json
        {
            "error": "string"
        }
        ```
        '''
        url = self.path("/posts/random", site_or_service)
        return await self.fetch(
            url,
            RespSolutionFuncs.json_resp_2("Unknown error"),
            required_status=[200, 404]
        )

    async def get_popular_posts(self, site_or_service: str, period: str = "recent", date: Optional[str] = None, offset: int = 0):
        '''
        `Status: 200 OK`
        ```json
        {
            "info": {
                "date": "string",
                "min_date": "string",
                "max_date": "string",
                "navigation_dates": {
                    "additionalProp1": [],
                    "additionalProp2": [],
                    "additionalProp3": []
                },
                "range_desc": "string",
                "scale": "recent"
            },
            "props": {
                "currentPage": "popular_posts",
                "today": "string",
                "earliest_date_for_popular": "string",
                "limit": 0,
                "count": 0
            },
            "results": [
                {
                    "id": "string",
                    "user": "string",
                    "service": "string",
                    "title": "string",
                    "content": "string",
                    "embed": {},
                    "shared_file": true,
                    "added": "string",
                    "published": "string",
                    "edited": "string",
                    "file": {},
                    "attachments": [
                        {}
                    ],
                    "fav_count": 0
                }
            ],
            "base": {
                "additionalProp1": "string",
                "additionalProp2": "string",
                "additionalProp3": "string"
            },
            "result_previews": [
                {
                    "type": "thumbnail",
                    "server": "string",
                    "name": "string",
                    "path": "string"
                },
                {
                    "type": "embed",
                    "url": "string",
                    "subject": "string",
                    "description": "string"
                }
            ],
            "result_attachments": [
                {
                    "server": "string",
                    "name": "string",
                    "path": "string"
                }
            ],
            "result_is_image": [
                true
            ]
        }
        ```
        '''
        if offset % 50 != 0:
            raise ValueError("Offset must be a multiple of 50")
        if period not in ["recent", "day", "week", "month"]:
            raise ValueError(f"Invalid period {period}")
        url = self.path("/posts/popular", site_or_service, query={"period": period, "date": date, "offset": offset})
        return await self.fetch(url)
    
    async def get_post_tags(self, site_or_service: str):
        '''
        `Status: 200 OK`
        ```json
        {
            "props": {
                "currentpage": "tags"
            },
            "tags": [
                {
                    "tag": "string",
                    "post_count": 0
                }
            ]
        }
        ```
        '''
        url = self.path("/posts/tags", site_or_service)
        return await self.fetch(url)

    async def get_archive_content(self, site_or_service, file_hash: str):
        '''
        `Status: 200 OK`
        ```json
        {
            "archive": {
                "file": {
                    "id": 0,
                    "hash": "string",
                    "mtime": "string",
                    "ctime": "string",
                    "mime": "string",
                    "ext": "string",
                    "added": "string",
                    "size": 0,
                    "ihash": "string"
                },
            "file_list": [
                "string"
            ],
                "password": "string"
            },
            "file_serving_enabled": true
        }
        ```
        '''
        url = self.path("/posts/archives/{file_hash}", site_or_service, format={"file_hash": file_hash})
        return await self.fetch(url)

    
    ##################################### Manual API #####################################
    async def get_creator_posts_posts_count(self, service: str, creator_id: str):
        site = get_service_site(service)
        content = await self.fetch(
            f"https://{site}.su/{service}/user/{creator_id}",
            RespSolutionFuncs.text_resp(),
            headers={"Referer": f"https://{site}.su/artists"}
        )
        if not content:
            raise PartySuAPIError("Failed to fetch creator posts count")
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
    
    async def get_archive_details(self, site_or_service: str, file_hash: str):
        site = get_service_site(site_or_service)
        content = await self.fetch(
            f"https://{site}.su/posts/archives/{file_hash}",
            RespSolutionFuncs.text_resp(),
        )
        if not content:
            raise PartySuAPIError("Failed to fetch archive details")
        soup = BeautifulSoup(content, "html.parser")
        text = soup.find(attrs={"class": "main", "id": "main"}).text
        lines = [line.strip() for line in text.split("\n") if line.strip() and not line.startswith("Archive Files")]
        if lines and lines[0] == "File does not exist or is not an archive.":
            raise PartySuAPIError("File does not exist or is not an archive.")
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
        _, service = get_user_id_service_by_hash_id(user_hash_id)
        site = get_service_site(service)
        raw_user_data = await self.api.kemono_users.get_raw_user(site, user_hash_id)
        if raw_user_data is None:
            return None
        link_accounts = await self.api.get_creator_links_accounts(raw_user_data.get("service"), raw_user_data.get("id"))
        await self.api.check_link_accounts_data(link_accounts, site)
        if self.api.kemono_users._get_data(site) is None:
            await self.api.kemono_users.refresh_data(site)
        creator = build_kemono_creator(raw_user_data, link_accounts, self.api.kemono_users._get_data(site))
        return creator
    
    async def create_creator(self, user_hash_id):
        if user_hash_id in self.mapping:
            # need try update
            return None
        async with self._lock:
            creator = await self.build_creator(user_hash_id)
            if creator is None:
                raise PartySuAPIError(f"Failed to build creator with user {user_hash_id}, check user_id and service")
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
        self._kemono_data: Optional[dict] = None
        self._coomer_data: Optional[dict] = None
        self._kemono_cache: dict[str, KemonoUser] = {}
        self._coomer_cache: dict[str, KemonoUser] = {}
        self.refresh_lock = asyncio.Lock()
        self.refresh_interval = 60*5 # 5 minutes
        self._kemono_last_refresh = None
        self._coomer_last_refresh = None
    
    def _get_last_refresh(self, site: str):
        if site == "kemono":
            return self._kemono_last_refresh
        elif site == "coomer":
            return self._coomer_last_refresh
        else:
            raise ValueError("Invalid site")
    
    def _set_last_refresh(self, site: str, last_refresh):
        if site == "kemono":
            self._kemono_last_refresh = last_refresh
        elif site == "coomer":
            self._coomer_last_refresh = last_refresh
        else:
            raise ValueError("Invalid site")
    
    def _get_data(self, site):
        if site == "kemono":
            return self._kemono_data
        elif site == "coomer":
            return self._coomer_data
        else:
            raise ValueError("Invalid site")
    
    def _set_data(self, site, data):
        if site == "kemono":
            self._kemono_data = data
        elif site == "coomer":
            self._coomer_data = data
        else:
            raise ValueError("Invalid site")
    
    def _get_cache(self, site: str):
        if site == "kemono":
            return self._kemono_cache
        elif site == "coomer":
            return self._coomer_cache
        else:
            raise ValueError("Invalid site")
    
    def _set_cache(self, site: str, cache: dict):
        if site == "kemono":
            self._kemono_cache = cache
        elif site == "coomer":
            self._coomer_cache = cache
        else:
            raise ValueError("Invalid site")
    
    async def fetch_data(self, site: str):
        if site is None:
            await asyncio.gather(self._fetch_data("kemono"), self._fetch_data("coomer"))
        else:
            await self._fetch_data(site)
    
    async def _fetch_data(self, site: str):
        data = await self.api.list_creators(site)
        if data is None:
            data = json_load(f"data/cache/{site}_creators.json")
            if data is None:
                raise PartySuAPIError("Failed to fetch creators data")
        else:
            self._set_cache(site, {})
            json_dump(data, f"data/cache/{site}_creators.json")
        map = {user_hash_id_func(d.get("id"), d.get("service")): d for d in data}
        self._set_data(site, map)
    
    def _check_interval(self, site: str, interval=None):
        if interval is None:
            interval = self.refresh_interval
        last_refresh = self._get_last_refresh(site)
        return last_refresh is not None and asyncio.get_running_loop().time() - last_refresh > interval
    
    async def refresh_data(self, site, interval=None):
        if interval is not None and not self._check_interval(site, interval):
            return
        await self.fetch_data(site)
        await self.api.kemono_creators._refresh()
        self._set_last_refresh(site, asyncio.get_running_loop().time())
    
    async def get_raw_user(self, site: str, user_id, service=None, refresh=False):
        async with self.refresh_lock:
            data = self._get_data(site)
            if data is None or refresh or self._get_last_refresh(site) is None or \
                    self._check_interval(site):
                await self.refresh_data(site)
                data = self._get_data(site)
            user_hash_id = user_hash_id_func(user_id, service) if service is not None else user_id
            return data.get(user_hash_id)
    
    async def get_user(self, user_id, service=None, refresh=False, no_creator=False):
        async with self.refresh_lock:
            if service is None:
                _, service = get_user_id_service_by_hash_id(user_id)
            site = get_service_site(service)
            data = self._get_data(site)
            if data is None or refresh or self._get_last_refresh(site) is None or \
                    self._check_interval(site):
                await self.refresh_data(site)
                data = self._get_data(site)
            user_hash_id = user_hash_id_func(user_id, service) if service is not None else user_id
            cache = self._get_cache(site)
            kemono_user = cache.get(user_hash_id)
            if kemono_user is None:
                kemono_user = data.get(user_hash_id)
                if kemono_user is None:
                    raise PartySuAPIError(f"Kemono User {user_id} not found")
                link_accounts = await self.api.get_creator_links_accounts(kemono_user.get("service"), kemono_user.get("id"))
                if link_accounts is None:
                    logger.warning(f"Failed to fetch link accounts for {user_id}")
                    link_accounts = []
                
                if creator := await self.api.kemono_creators._get_creator(user_hash_id):
                    no_creator = True
                kemono_user: KemonoUserCreate = build_kemono_user_by_kwd(no_creator=no_creator, link_accounts=link_accounts, **kemono_user)
                if no_creator and creator:
                    kemono_user.kemono_creator = creator
                cache[user_hash_id] = kemono_user
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
            raise PartySuAPIError("Failed to fetch posts")
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


class KemonoAPI(BasePartySuAPI):
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
        post_count, posts_legacy = await asyncio.gather(self.get_creator_posts_posts_count(service, creator_id), self.get_creator_posts_legacy(service, creator_id))
        post_count_legacy = posts_legacy.get("props", {}).get("count") if posts_legacy is not None else None
        if post_count != post_count_legacy:
            if not post_count and post_count_legacy:
                post_count = post_count_legacy
            elif post_count and not post_count_legacy:
                pass
            else:
                raise PartySuAPIError(f"Post count mismatch: document count {post_count} <=> legacy api count {post_count_legacy}")
        if post_count is None:
            raise PartySuAPIInvalidResponse("Failed to fetch post count")
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
                raise PartySuAPIError("Failed to fetch posts")
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
                raise PartySuAPIError("Timeout error: Failed to fetch posts")

            # Cancel extra tasks after end_page
            for task in tasks[end_page+1:]:
                task.cancel()

        await asyncio.gather(fetch_page(), main_task())

        # Collect results
        posts = []
        results = await asyncio.gather(*tasks[:end_page+1], return_exceptions=True)
        for result in results:
            if isinstance(result, Exception) or result.get("data") is None:
                raise PartySuAPIError("Failed to fetch posts")
            posts.extend(result.get("data"))

        return posts
    
    async def get_discord_server_all_posts(self, server_id: str):
        channels = await self.lookup_discord_channels(server_id)
        if channels is None:
            raise PartySuAPIError("Failed to fetch channels")
        all_posts = []
        for channel in channels:
            channel_id = channel.get("id")
            channel_name = channel.get("name")
            logger.info(f"Fetching posts from {channel_name} ({channel_id})")
            try:
                posts = await self.get_discord_channel_all_posts(channel_id)
            except PartySuAPIError as e:
                logger.warning(f"Failed to fetch posts from {channel_name} ({channel_id}): {e}")
                continue
            all_posts.extend(posts)
        return all_posts
    
    async def check_link_accounts_data(self, accounts: list[dict], site: Optional[str] = None):
        '''
        Some link accounts may not exist in users data, remove them.
        '''
        if not accounts:
            return
        if site is None:
            site = get_service_site(accounts[0].get("service"))
        await self.kemono_users.refresh_data(site, 60*3)
        data = self.kemono_users._get_data(site)
        for i in range(len(accounts) -1, -1, -1):
            hash_id = user_hash_id_func(accounts[i].get("id"), accounts[i].get("service"))
            if hash_id not in data:
                logger.warning(f"Link account {hash_id} not found in users data, remove it.")
                accounts.pop(i)
