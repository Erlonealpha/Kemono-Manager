from sqlmodel import select
from typing import Type
from kemonobakend.database.models import KemonoCreatorCreate, KemonoCreator
from kemonobakend.database.model_builder import build_kemono_user_by_kwd

from .base import BaseSessionHandle

class KemonoCreatorHandle(BaseSessionHandle):
    __model__class__: Type[KemonoCreator] = KemonoCreator
    async def add_creator(self, creator: KemonoCreatorCreate, commit: bool = True) -> KemonoCreator:
        kemono_creator = creator.to_sqlmodel()
        return await self.add(kemono_creator, commit=commit)
    
    async def get_creator_by_name(self, name: str) -> KemonoCreator:
        statement = select(KemonoCreator).where(KemonoCreator.name == name)
        result = (await self.session.exec(statement)).first()
        return result
