from .combine import AsyncCombineSession, KemonoUserHandle, KemonoPostHandle, KemonoAttachmentHandle

class AsyncKemonoSession(AsyncCombineSession):
    __set_handlers__ = (KemonoUserHandle, KemonoPostHandle, KemonoAttachmentHandle)

    async def add_kemono_user(self, id_or_hash_id = None, service = None, url = None):
        pass