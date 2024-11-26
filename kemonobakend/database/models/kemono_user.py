# from .kemono_creator import KemonoUser
from sqlmodel import Field, Relationship
from typing import Optional
from .base import Base

class KemonoUserBase(Base):
    user_id: str         = Field(nullable=False)
    
    favorited: int       = Field(default=None, nullable=True)
    indexed: int         = Field(default=None, nullable=True)
    name: str            = Field(default=None, nullable=True)
    service: str         = Field(nullable=False)
    updated: int         = Field(default=None, nullable=True)
    link_accounts: str   = Field(default="[]", description="JSON array of linked accounts(user_hash_id)")

    public_name: str     = Field(nullable=False)
    creator_hash_id: str = Field(nullable=False, foreign_key="kemono_creator.hash_id")

class KemonoUserCreate(KemonoUserBase):
    kemono_creator: "KemonoCreatorCreate" = None
    
    def to_sqlmodel(self):
        return KemonoUser(**self.model_dump(exclude={"kemono_creator"}))

class KemonoUser(KemonoUserBase, table=True):
    __tablename__ = "kemono_user"
    __name__ = "Kemono user"
    id: Optional[int] = Field(default=None, primary_key=True)
    kemono_creator: "KemonoCreator" = Relationship(
        back_populates="kemono_users", 
        sa_relationship_kwargs={"lazy": "subquery"}
    )

from kemonobakend.database.models.kemono_creator import KemonoCreator, KemonoCreatorCreate