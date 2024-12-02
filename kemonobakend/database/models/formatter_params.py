from sqlmodel import Field
from typing import Optional

from .base import Base

class FormatterParamsBase(Base):
    formatter_name: str
    param_json: str
    param_version: Optional[str] = Field(default="v1.0.0")

class FormatterParamsCreate(FormatterParamsBase):
    pass
    def to_sqlmodel(self):
        return FormatterParams(**self.model_dump())

class FormatterParams(FormatterParamsBase, table=True):
    __tablename__ = "formatter_params"
    id: Optional[int] = Field(default=None, primary_key=True)