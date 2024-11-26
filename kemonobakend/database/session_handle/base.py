from sqlmodel import SQLModel, select, or_
from sqlmodel.sql.expression import SelectOfScalar
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException

from typing import Type, TypeVar
from kemonobakend.database.models import Base

T = TypeVar("T", bound=Base)

class BaseSessionHandle:
    __model__class__: Type[T]
    def __init__(self, session: AsyncSession):
        self.session = session
        if self.__model__class__ is None:
            raise NotImplementedError("Model class not defined")
    
    async def add(self, obj: T, commit: bool = True):
        self.session.add(obj)
        if commit:
            await self.session.commit()
            await self.session.refresh(obj)
        return obj

    async def add_all(self, objs: list[T], commit: bool = True) -> None:
        self.session.add_all(objs)
        if commit:
            await self.session.commit()

    async def delete(self, obj: T, commit: bool = True):
        await self.session.delete(obj)
        if commit:
            await self.session.commit()
    
    async def delete_all(self, objs: list[T], commit: bool = True) -> None:
        for obj in objs:
            await self.delete(obj, commit=False)
        if commit:
            await self.session.commit()
    
    async def update(self, obj: T, commit: bool = True):
        return await self.add(obj, commit)

    async def get(self, hash_id: str):
        statement = select(self.__model__class__).where(
            self.__model__class__.hash_id == hash_id
        )
        results = await self.session.exec(statement)
        result = results.first()
        return result

    async def get_all(self):
        statement = select(self.__model__class__)
        results = await self.session.exec(statement)
        try:
            return results.unique().all()
        except Exception as e: # TODO: find a better way to handle this
            return results.unique().all()
    
    async def fetch_one(self, statement: SelectOfScalar[T]):
        results = await self.session.exec(statement)
        return results.first()
    
    async def fetch_all(self, statement: SelectOfScalar[T]):
        results = await self.session.exec(statement)
        return results.all()

    async def search(self, query: dict):
        exprs = (
            getattr(self.__model__class__, key).ilike(f"%{value}%")
            for key, value in query.items()
            if hasattr(self.__model__class__, key)
        )
        statement = select(self.__model__class__).where(
            or_(
                *exprs
            )
        )
        results = await self.session.exec(statement)
        return results.all()