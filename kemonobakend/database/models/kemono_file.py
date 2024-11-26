from sqlmodel import Field, Relationship
from typing import Optional

from .base import Base

class KemonoFileBase(Base):
    idx: int
    sha256: Optional[str] = Field(default=None)
    save_path: str
    root: str
    folder: str
    file_name: str
    file_size: Optional[int] = Field(default=None)
    file_type: Optional[str] = Field(default=None)

    formatter_name: str = Field(index=True)
    attachment_hash_id: str = Field(foreign_key="kemono_attachment.hash_id")
    post_hash_id: str = Field(foreign_key="kemono_post.hash_id")
    user_hash_id: str = Field(foreign_key="kemono_user.hash_id", index=True)

class KemonoFileCreate(KemonoFileBase):
    def to_sqlmodel(self):
        return KemonoFile(**self.model_dump())

class KemonoFile(KemonoFileBase, table=True):
    __tablename__ = "kemono_file"
    __name__ = "Kemono file"
    id: Optional[int] = Field(default=None, primary_key=True)