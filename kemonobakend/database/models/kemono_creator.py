from sqlmodel import Field, Relationship
from typing import Optional
from .base import Base

class KemonoCreatorBase(Base):
    name: str
    name_from: str
    relation_id: Optional[int] = Field(default=None)
    public_user_hash_id: str

class KemonoCreatorCreate(KemonoCreatorBase):
    kemono_users: list["KemonoUserCreate"] =  None
    
    def to_sqlmodel(self) -> 'KemonoCreator':
        kwd = self.model_dump(exclude={"kemono_users"})
        return KemonoCreator(**kwd)

class KemonoCreator(KemonoCreatorBase, table=True):
    __tablename__ = "kemono_creator"
    __name__ = "Kemono creator"
    id: Optional[int] = Field(default=None, primary_key=True)
    kemono_users: list["KemonoUser"] = Relationship(
        back_populates="kemono_creator", 
        sa_relationship_kwargs={"lazy": "subquery"},
    )

from kemonobakend.database.models.kemono_user import KemonoUser, KemonoUserCreate