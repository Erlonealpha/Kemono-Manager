from sqlmodel import select
from typing import Union, Type, Tuple
from kemonobakend.database.models import KemonoFile, KemonoFileCreate
from kemonobakend.database.model_builder import build_kemono_file_by_kwd

from .base import BaseSessionHandle


class KemonoFileHandle(BaseSessionHandle):
    __model__class__: Type[KemonoFile] = KemonoFile
    async def add_file_by_kwd(self, **kwd):
        file = build_kemono_file_by_kwd(**kwd)
        file = await self.add(file)
        return file
    
    async def add_files(self, files: list[Union[KemonoFile, KemonoFileCreate]], commit: bool = True):
        if not files:
            return
        if isinstance(files[0], KemonoFileCreate):
            files = [file.to_sqlmodel() for file in files]
        await self.add_all(files, commit=commit)

    async def get_files_by_formatter_name(self, formatter_name: str):
        statement = select(KemonoFile).where(KemonoFile.formatter_name == formatter_name)
        return (await self.session.exec(statement)).all()
    
    async def get_files_by_user(self, user_hash_id: str):
        statement = select(KemonoFile).where(KemonoFile.user_hash_id == user_hash_id)
        return (await self.session.exec(statement)).all()
    
    async def get_files_by_post(self, post_hash_id: str):
        statement = select(KemonoFile).where(KemonoFile.post_hash_id == post_hash_id)
        return (await self.session.exec(statement)).all()
    
    async def delete_files_by_formatter_name(self, formatter_name: str, commit: bool = True):
        statement = select(KemonoFile).where(KemonoFile.formatter_name == formatter_name)
        files = (await self.session.exec(statement)).all()
        try:
            for file in files:
                await self.delete(file, commit=False)
            if commit:
                await self.session.commit()
        except Exception as e:
            return False
        return True