from sqlmodel import select
from typing import Type
from datetime import datetime
from kemonobakend.database.models import KemonoPostsInfoCreate, KemonoPostsInfo
from kemonobakend.database.model_builder import build_kemono_user_by_kwd

from .base import BaseSessionHandle

class KemonoPostsInfoHandle(BaseSessionHandle):
    __model__class__: Type[KemonoPostsInfo] = KemonoPostsInfo
    async def add_info(self, kemono_posts_info: KemonoPostsInfoCreate, commit: bool = True) -> KemonoPostsInfo:
        if kemono_posts_info.added_at is None:
            kemono_posts_info.added_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        info = kemono_posts_info.to_sqlmodel()
        return await self.add(info, commit=commit)

    async def update_info(self, kemono_posts_info: KemonoPostsInfo, commit: bool = True) -> KemonoPostsInfo:
        if kemono_posts_info.updated_at is None:
            kemono_posts_info.updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        else: 
            kemono_posts_info.updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return await self.update(kemono_posts_info, commit=commit)
    
    async def get_info_by_hash_id(self, hash_id: str) -> KemonoPostsInfo:
        statement = select(KemonoPostsInfo).where(KemonoPostsInfo.hash_id == hash_id)
        return await self.fetch_one(statement)
    
    async def get_info_by_user_hash_id(self, user_hash_id: str) -> KemonoPostsInfo:
        statement = select(KemonoPostsInfo).where(KemonoPostsInfo.user_hash_id == user_hash_id)
        return await self.fetch_one(statement)