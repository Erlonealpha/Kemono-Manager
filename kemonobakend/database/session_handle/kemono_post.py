from sqlmodel import select
from fastapi import HTTPException
from typing import Type
from kemonobakend.database.models import KemonoPost, KemonoPostCreate
from kemonobakend.database.model_builder import build_kemono_post
from .base import BaseSessionHandle

class KemonoPostHandle(BaseSessionHandle):
    __model__class__: Type[KemonoPost] = KemonoPost
    async def add_post(self, post: KemonoPostCreate, commit: bool = True):
        post = post.to_sqlmodel()
        return await self.add(post, commit)
    
    async def add_posts(self, posts: list[KemonoPostCreate], commit: bool = True):
        posts = [post.to_sqlmodel() for post in posts]
        return await self.add_all(posts, commit)
    
    async def add_post_by_kwd(self, commit: bool = True, **kwargs) -> KemonoPost:
        try:
            post = build_kemono_post(**kwargs)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        return await self.add(post, commit)

    async def get_posts_by_user(self, user_hash_id: str):
        statement = select(KemonoPost).where(KemonoPost.user_hash_id == user_hash_id)
        results = await self.session.exec(statement)
        return results.unique().all()
    
    async def delete_all_by_user(self, user_hash_id: str, commit: bool = True):
        statement = select(KemonoPost).where(KemonoPost.user_hash_id == user_hash_id)
        results = await self.session.exec(statement)
        posts = results.all()
        await self.delete_all(posts, commit)
    
    async def delete_all_by_info(self, posts_info_hash_id: str, commit: bool = True):
        statement = select(KemonoPost).where(KemonoPost.posts_info_hash_id == posts_info_hash_id)
        results = await self.fetch_all(statement)
        await self.delete_all(results, commit)

