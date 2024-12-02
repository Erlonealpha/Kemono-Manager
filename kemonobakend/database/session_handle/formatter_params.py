from sqlmodel import select
from typing import Union, Type, Tuple
from kemonobakend.database.models import FormatterParamsCreate, FormatterParams
from kemonobakend.database.model_builder import build_formatter_param
from .base import BaseSessionHandle

class FormatterParamsHandle(BaseSessionHandle):
    __model__class__: Type[FormatterParams] = FormatterParams
    async def add_param(self, param: FormatterParamsCreate, commit: bool = True):
        param = param.to_sqlmodel()
        return await self.add(param, commit=commit)
    
    async def get_param(self, formatter_name: str):
        statement = select(FormatterParams).where(FormatterParams.formatter_name == formatter_name)
        return await self.fetch_one(statement)
    
    async def add_param_by_kwd(self, formatter_name: str, commit = True, **kwargs):
        param = build_formatter_param(formatter_name, **kwargs)
        return await self.add_param(param, commit=commit)