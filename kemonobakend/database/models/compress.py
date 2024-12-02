from sqlmodel import Field, Relationship
from typing import Optional

from .base import Base


class CompressBase(Base):
    sha256: str
    type: str = Field(description="Compression type, e.g. 'zip', 'rar', '7z', etc.")
    encrypted: Optional[bool] = Field(default=False)
    password: Optional[str] = Field(default=None)

class CompressCreate(CompressBase):
    paths: list[str] = None

    def to_sqlmodel(self):
        return Compress(**self.model_dump(exclude={"paths"}))


class Compress(CompressBase):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    paths: list["CompressPath"] = Relationship(
        back_populates="compress", 
        link_model="CompressReadPath", 
        sa_relationship_kwargs={"lazy": "joined"}
    )


class CompressReadBase(Base):
    path: str
    compress_sha256: str
    path_sha256: Optional[str] = Field(default=None)
    compress_hash_id: str = Field(foreign_key="compress.hash_id")
    type: str = Field(description="path type, e.g. 'file', 'directory', 'link', etc.")

class CompressPathCreate(CompressReadBase):
    compress: Compress = None

    def to_sqlmodel(self):
        return CompressPath(**self.model_dump(exclude={"compress"}))

class CompressPath(CompressReadBase):
    id: Optional[int] = Field(default=None, primary_key=True)

    compress: Compress = Relationship(
        back_populates="paths", 
        link_model="CompressRead", 
        sa_relationship_kwargs={"lazy": "joined"}
    )