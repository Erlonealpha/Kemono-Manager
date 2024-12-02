from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Union, Coroutine, Type, TypeVar, Any

from .file_name_todo import FileNameZFillerToDo, NumWithZFiller

_OT = TypeVar("_OT")
_ST = TypeVar("_ST")
_RT = TypeVar("_RT")

class AbstractFilesFormatter(ABC):
    __outer_packaging_class__: Type[_OT]
    __source_class__: Type[_ST]
    __return_class__: Type[_RT]
    
    folder_dic: defaultdict[str, tuple['NumWithZFiller', list[_RT]]]
    folder_count_dic: defaultdict[str, int]
    page_dic: defaultdict[str, tuple['NumWithZFiller', list[_RT]]]
    
    @abstractmethod
    def __init__(self, root: str, folder_expr: str = None, file_expr: str = None): ...
    
    @abstractmethod
    async def generate_files(self, outers: list[_OT]) -> list[_RT]: ...
    
    @staticmethod
    @abstractmethod
    def default_folder_expr() -> str: ...
    
    @staticmethod
    @abstractmethod
    def default_file_expr() -> str: ...

    @staticmethod
    @abstractmethod
    def init_folder_dic_item(start_num: int, min_enable_count: int, min_length: int) -> tuple['NumWithZFiller', list[_ST]]: ...
    
    @staticmethod
    @abstractmethod
    def get_files(files) -> list[_ST]: ...
    
    @staticmethod
    @abstractmethod
    def get_file_hash(file: _ST) -> str: ...
    
    @abstractmethod
    async def remove_duplicate_files(self, sources: list[_ST]): ...
    
    @abstractmethod
    def sort_outers(self, outers: list[_OT]): ...
    
    @abstractmethod
    def sort_files(self, sources: list[_ST], reverse: bool = False): ...
    
    @abstractmethod
    async def format_folder_and_file_name(self, local: dict, outer: _OT, source: _ST, **kwargs) -> tuple[str, str]: ...
    
    @abstractmethod
    def get_folder_actual(self, folder: str) -> str: ...
    
    @abstractmethod
    async def handle_serial_num(self, local: dict, outer: _OT, source: _ST, **kwargs) -> int: ...
    
    @abstractmethod
    def handle_max_single_folder_files(self, local: dict, outer: _OT, source: _ST, **kwargs): ...
    
    @abstractmethod
    async def handle_page_num(self, local: dict, outer: _OT, source: _ST, **kwargs) -> int: ...
    
    @abstractmethod
    def get_page_based(self, local: dict, outer: _OT, source: _ST, **kwargs) -> str: ...
    
    @abstractmethod
    def build_return_object(self, local: dict, outer: _OT, source: _ST, file_name_zfiller: 'FileNameZFillerToDo', **kwargs) -> _RT: ...
    
    @abstractmethod
    def file_name_todo(): ...


