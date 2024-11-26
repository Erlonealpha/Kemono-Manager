from sqlmodel import Field, Relationship
from typing import Optional
from .base import Base

class KemonoPostsInfoBase(Base):
    user_hash_id: str = Field(foreign_key="kemono_user.hash_id")
    updated: int = Field(description="Last update timestamp of the posts in kemono server")
    posts_length: int
    added_at: Optional[str] = Field(default=None, description="Date when the posts was added in program")
    updated_at: Optional[str] = Field(default=None, description="Date when the posts was updated in program")

class KemonoPostsInfoCreate(KemonoPostsInfoBase):
    posts: list["KemonoPostCreate"] = []
    
    def to_sqlmodel(self):
        return KemonoPostsInfo(**self.model_dump(exclude={"posts"}))

class KemonoPostsInfo(KemonoPostsInfoBase, table=True):
    __tablename__ = "kemono_posts_info"
    id: Optional[int] = Field(default=None, primary_key=True)
    
    posts: list["KemonoPost"] = Relationship(back_populates="info", sa_relationship_kwargs={"lazy": "joined"})


from kemonobakend.database.models.kemono_post import KemonoPost, KemonoPostCreate