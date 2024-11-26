from sqlmodel import select, or_
from typing import Type
from kemonobakend.database.models import KemonoUser, KemonoUserCreate
from kemonobakend.database.model_builder import build_kemono_user_by_kwd
from kemonobakend.kemono.builtins import user_hash_id_func

from .base import BaseSessionHandle

class KemonoUserHandle(BaseSessionHandle):
    __model__class__: Type[KemonoUser] = KemonoUser
    async def add_user(self, user: KemonoUserCreate, commit: bool = True):
        user = user.to_sqlmodel()
        return await self.add(user, commit)
    
    async def add_user_by_kwd(self, commit: bool = True, **kwargs) -> KemonoUser:
        user = build_kemono_user_by_kwd(**kwargs)
        return await self.add(user, commit)
    
    async def has_user(self, hash_id: str) -> bool:
        statement = select(KemonoUser).where(KemonoUser.hash_id == hash_id)
        res = await self.session.exec(statement)
        return len(res.all()) > 0
    
    async def get_user(self, hash_id: str, all_users: bool = False) -> KemonoUser:
        statement = select(KemonoUser).where(KemonoUser.hash_id == hash_id)
        user = await self.fetch_one(statement)
        if user and all_users:
            await self.session.run_sync(lambda _ : user.kemono_creator.kemono_users)
        return user

    async def get_users(self, user_hash_ids: list[str]) -> list[KemonoUser]:
        if not user_hash_ids:
            return []
        statement = select(KemonoUser).where(or_(KemonoUser.hash_id == hash_id for hash_id in user_hash_ids))
        return await self.fetch_all(statement)
    
    async def get_users_by_link_accounts(self, link_accounts: list[dict]):
        if not link_accounts:
            return []
        hash_ids = [user_hash_id_func(link_account["id"], link_account["service"]) for link_account in link_accounts]
        return await self.get_users(hash_ids)