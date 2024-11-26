from sqlmodel import Field, Relationship
from typing import Optional

from .base import Base

class KemonoAttachmentBase(Base):
    name: str             = Field(nullable=False)
    path: str             = Field(nullable=False)
    type: str             = Field(default="normal", nullable=False) # normal or cover or thumbnail
    size: Optional[int]   = Field(default=None, nullable=True)
    sha256: Optional[str] = Field(default=None, nullable=True)
    idx: Optional[int]    = Field(default=None, nullable=True)
    user_hash_id: str     = Field(nullable=False, foreign_key="kemono_user.hash_id", index=True)
    post_hash_id: str     = Field(nullable=False, foreign_key="kemono_post.hash_id")

class KemonoAttachmentCreate(KemonoAttachmentBase):
    post: "KemonoPostCreate" = None
    
    def to_sqlmodel(self) -> 'KemonoAttachment':
        kwd = self.model_dump(exclude={"post"})
        return KemonoAttachment(**kwd)

class KemonoAttachment(KemonoAttachmentBase, table=True):
    __tablename__ = "kemono_attachment"
    __name__ = "Kemono attachment"
    id: Optional[int] = Field(default=None, primary_key=True)
    
    post: "KemonoPost" = Relationship(back_populates="attachments", sa_relationship_kwargs={"lazy": "joined"})


from kemonobakend.database.models.kemono_post import KemonoPostCreate, KemonoPost