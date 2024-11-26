from sqlmodel import select
from typing import Union, Type, Tuple
from kemonobakend.database.models import KemonoAttachment, KemonoAttachmentCreate, KemonoPost
from kemonobakend.database.model_builder import build_kemono_attachments
from .base import BaseSessionHandle

class KemonoAttachmentHandle(BaseSessionHandle):
    __model__class__: Type[KemonoAttachment] = KemonoAttachment
    async def add_attachments(self, attachments: list[KemonoAttachmentCreate], commit: bool = True):
        attachments = [
            attachment.to_sqlmodel()
            for attachment in attachments
        ]
        await self.add_all(attachments, commit)
    
    async def add_attachments_by_kwds(self, args: list[dict], post_hash_id: str = None):
        attachments = build_kemono_attachments(post_hash_id, args)
        await self.add_all(attachments)
    
    
    async def get_attachments_by_user(self, user_hash_id: str) -> Union[Tuple[list[KemonoAttachment], list[KemonoPost]], list[KemonoAttachment]]:
        statement = select(KemonoAttachment).where(KemonoAttachment.user_hash_id == user_hash_id)
        attachments = (await self.session.exec(statement)).unique().all()
        return attachments
    
    async def get_attachments_kwds_by_post(self, post_hash_id: str):
        statement = select(KemonoAttachment).where(KemonoAttachment.post_hash_id == post_hash_id)
        results = await self.session.exec(statement)
        return results.unique().all()

    async def delete_all_by_user(self, user_hash_id: str, commit: bool = True):
        attachments = await self.get_attachments_by_user(user_hash_id)
        await self.delete_all(attachments, commit)