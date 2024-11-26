from sqlmodel import Field
from typing import Optional

from .base import Base

class FormatterParamBase(Base):
    formatter_name: str
    param_json: str
    param_version: Optional[str] = Field(default="v1.0.0")

class FormatterParamCreate(FormatterParamBase):
    pass
    def to_sqlmodel(self):
        return FormatterParam(**self.model_dump())

class FormatterParam(FormatterParamBase, table=True):
    __tablename__ = "formatter_params"
    id: Optional[int] = Field(default=None, primary_key=True)