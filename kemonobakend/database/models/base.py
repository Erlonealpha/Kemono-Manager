from sqlmodel import SQLModel, Field
from typing import Optional

class Base(SQLModel):
    hash_id: Optional[str] = Field(nullable=False)
    hash_id_type: Optional[str] = Field(default="base")