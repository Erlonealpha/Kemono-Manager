from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine
from typing import Optional, Tuple, Type

from kemonobakend.database.models import *
from kemonobakend.database.session_handle import (
    BaseSessionHandle,
    
    KemonoCreatorHandle, KemonoUserHandle, KemonoPostHandle,
    KemonoPostsInfoHandle, KemonoAttachmentHandle, KemonoFileHandle,
    FormatterParamsHandle
)
from .engine import engine as e

class AbsHandler:
    __builtin_handlers__ = (
        KemonoCreatorHandle, KemonoUserHandle, KemonoPostHandle, 
        KemonoPostsInfoHandle, KemonoAttachmentHandle, KemonoFileHandle,
        FormatterParamsHandle
    )
    __builtin_handlers_map__ = {
        "KemonoCreatorHandle": "kemono_creator",
        "KemonoUserHandle": "kemono_user",
        "KemonoPostHandle": "kemono_post",
        "KemonoPostsInfoHandle": "kemono_posts_info",
        "KemonoAttachmentHandle": "kemono_attachment",
        "KemonoFileHandle": "kemono_file",
        "FormatterParamsHandle": "formatter_params"
    }
    kemono_creator: KemonoCreatorHandle
    kemono_user: KemonoUserHandle
    kemono_post: KemonoPostHandle
    kemono_posts_info: KemonoPostsInfoHandle
    kemono_attachment: KemonoAttachmentHandle
    kemono_file: KemonoFileHandle
    formatter_params: FormatterParamsHandle

async def create_all(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def drop_all(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

class AsyncCombineSession(AsyncSession, AbsHandler):
    __set_handlers__ = AbsHandler.__builtin_handlers__
    def __init__(self, engine: AsyncEngine = e, include_handlers: Optional[Tuple[Type[BaseSessionHandle]]]=None):
        self.engine = engine
        super().__init__(engine)
        if include_handlers is None:
            include_handlers = self.__set_handlers__
        
        for handler in self.__set_handlers__:
            self.__setattr_by_handler__(handler, handler(self))
    
    def __getattr_by_handler__(self, handler: Type[BaseSessionHandle]) -> BaseSessionHandle:
        return getattr(self, self.__builtin_handlers_map__.get(handler.__name__))
    def __setattr_by_handler__(self, handler: Type[BaseSessionHandle], value) -> None:
        return setattr(self, self.__builtin_handlers_map__.get(handler.__name__), value)
    
    async def create_all(self):
        await create_all(self.engine)
    
    async def drop_all(self):
        await drop_all(self.engine)
    
    async def migrate(self):
        all_data = []
        for handler in self.__builtin_handlers__:
            handle = self.__getattr_by_handler__(handler)
            if handle is not None:
                data = await handle.get_all()
                all_data.append(data)
        await self.drop_all()
        await self.create_all()
        for handler, data in zip(self.__builtin_handlers__, all_data):
            handle = self.__getattr_by_handler__(handler)
            if handle is not None and data:
                await handle.add_all(data)