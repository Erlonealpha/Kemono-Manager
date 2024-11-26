from sqlmodel import select
from typing import Union, Type, Tuple
from kemonobakend.database.models import FormatterParamCreate, FormatterParam
from kemonobakend.database.model_builder import build_formatter_param
from .base import BaseSessionHandle

class FormatterParamHandle(BaseSessionHandle):
    __model__class__: Type[FormatterParam] = FormatterParam
    async def add_param(self, param: FormatterParamCreate, commit: bool = True):
        param = param.to_sqlmodel()
        return await self.add(param, commit=commit)
    
    async def get_param(self, formatter_name: str):
        statement = select(FormatterParam).where(FormatterParam.formatter_name == formatter_name)
        return await self.fetch_one(statement)
    
    async def add_param_by_kwd(self, formatter_name: str, commit = True, **kwargs):
        param = build_formatter_param(formatter_name, **kwargs)
        return await self.add_param(param, commit=commit)