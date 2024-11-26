# from .kemono_attachment import KemonoPost
from sqlmodel import Field, Relationship
from typing import Optional

from .base import Base

class PostBase(Base):
    post_id: str             = Field(nullable=False)
    service: str             = Field(nullable=False)
    content: str             = Field(default="")
    added: Optional[str]     = Field(default=None, nullable=True)
    published: Optional[str] = Field(default=None, nullable=True)
    edited: Optional[str]    = Field(default=None, nullable=True)
    embeds: str              = Field(default="[]", description="JSON str")
    links: str               = Field(default="[]", description="JSON str")
    user_hash_id: str        = Field(nullable=False, foreign_key="kemono_user.hash_id")
    posts_info_hash_id: str  = Field(nullable=False, foreign_key="kemono_posts_info.hash_id")

class DiscordChannelBase(PostBase):
    server_id: str      = Field(nullable=False)
    channel_id: str     = Field(nullable=False)
    author: str         = Field(default="{}", description="JSON str")
    mentions: str       = Field(default="[]", description="JSON str")

class KemonoPostBase(PostBase):
    user_id: str            = Field(nullable=False)
    title: Optional[str]    = Field(default="")
    shared_file: bool       = Field(default=False)
    poll: Optional[str]     = Field(default=None, nullable=True)
    captions: Optional[str] = Field(default=None, nullable=True)
    tags: Optional[str]     = Field(default=None, nullable=True)

class KemonoPostCreate(KemonoPostBase, DiscordChannelBase):
    attachments: list["KemonoAttachmentCreate"] = None
    info: "KemonoPostsInfoCreate" = None
    
    def to_sqlmodel(self):
        return KemonoPost(**self.model_dump(exclude={"attachments", "info"}))

class KemonoPost(KemonoPostBase, DiscordChannelBase, table=True):
    __tablename__ = "kemono_post"
    __name__ = "Kemono post"
    id: Optional[int]   = Field(default=None, primary_key=True)
    attachments: list["KemonoAttachment"] = Relationship(back_populates="post", sa_relationship_kwargs={"lazy": "joined"})
    info: "KemonoPostsInfo" = Relationship(back_populates="posts", sa_relationship_kwargs={"lazy": "joined"})


from kemonobakend.database.models.kemono_attachment import KemonoAttachment, KemonoAttachmentCreate
from kemonobakend.database.models.kemono_posts_info import KemonoPostsInfo, KemonoPostsInfoCreate