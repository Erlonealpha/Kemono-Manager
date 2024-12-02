from collections import defaultdict
from asyncstdlib.builtins import map as amap, list as alist
from typing import Union, Coroutine, Type, TypeVar, Any

from kemonobakend.utils import json_load, json_loads
from kemonobakend.log import logger
from kemonobakend.utils.run_code import RunCoder
from kemonobakend.database.models import FormatterParams

from .abs import AbstractFilesFormatter, _OT, _RT, _ST
from .file_name_todo import FileNameZFillerToDo, NumWithZFiller


class FilesFormatterBase(AbstractFilesFormatter):
    def __init__(
        self,
        formatter_name: str,
        root: str,
        folder_expr: str = None,
        file_expr: str = None,
        enable_serial: bool = True,
        serial_min_length: int = 2,
        serial_type: str = "same_folder",
        serial_start_num: int = 1,
        serial_ascending: bool = True,
        min_serial_enable_count: int = 2,
        enable_page_num: bool = True,
        page_num_min_length: int = 2,
        page_num_start: int = 1,
        page_num_include_types: list[str] = ["img", "video"],
        page_ascending: bool = True,
        min_page_enable_count: int = 2,
        allow_duplicate_file: bool = False,
        reserve_latest_duplicate_file: bool = True,
        max_single_folder_files: int = 2000,
        keep_files_continuous: bool = True,
    ):
        self.formatter_name = formatter_name
        self.root = root.replace("\\", "/")
        self.folder_coder = RunCoder(folder_expr or self.default_folder_expr())
        self.file_coder = RunCoder(file_expr or self.default_file_expr())
        self.enable_serial = enable_serial
        self.serial_min_length = serial_min_length
        self.serial_type = serial_type
        self.serial_start_num = serial_start_num
        self.serial_ascending = serial_ascending
        self.min_serial_enable_count = min_serial_enable_count
        self.enable_page_num = enable_page_num
        self.page_num_min_length = page_num_min_length
        self.page_num_start = page_num_start
        self.page_num_include_types = page_num_include_types
        self.page_ascending = page_ascending
        self.min_page_enable_count = min_page_enable_count
        self.allow_duplicate_file = allow_duplicate_file
        self.reserve_latest_duplicate_file = reserve_latest_duplicate_file
        self.max_single_folder_files = max_single_folder_files
        self.keep_files_continuous = keep_files_continuous
    
    @classmethod
    def from_config(cls, config: Union[dict, str]):
        if isinstance(config, str):
            config = json_load(config)
        return cls(
            **config,
        )
    
    @classmethod
    def from_formatter_params(cls, formatter_name: str, formatter_params: FormatterParams):
        params = json_loads(formatter_params.param_json)
        return cls(
            formatter_name,
            **params,
        )
    
    @staticmethod
    def init_folder_dic_item(start_num: int, min_enable_count: int, min_length: int):
        return [NumWithZFiller(start_num, min_enable_count, min_length), []]
    
    async def generate_files(self, outers: list[_OT], **kwargs) -> Coroutine[Any, Any, list[_RT]]:
        self.folder_dic = defaultdict(lambda: self.init_folder_dic_item(self.serial_start_num, self.min_serial_enable_count, self.serial_min_length))
        self.folder_count_dic = defaultdict(int)
        self.page_dic = defaultdict(lambda: self.init_folder_dic_item(self.page_num_start, self.min_page_enable_count, self.page_num_min_length))
        
        if not outers:
            return []
        self.sort_outers(outers)
        if not self.allow_duplicate_file:
            await self.remove_duplicate_files(outers)
        
        async def fn_outers(outer: _OT):
        
            async def fn_files(file: _ST):
                local = {}
                folder, file_name = await self.format_folder_and_file_name(local, outer, file, **kwargs)
                serial_num = await self.handle_serial_num(local, outer, file, folder=folder, file_name=file_name, **kwargs)
                page_num = await self.handle_page_num(local, outer, file, folder=folder, file_name=file_name, **kwargs)

                file_name_zfiller = FileNameZFillerToDo(
                    file_name,
                    serial_num,
                    page_num
                )
                
                obj = self.build_return_object(local, outer, file, file_name_zfiller, folder=folder, file_name=file_name, **kwargs)
                self.folder_dic[local["folder_actual"]][1].append(obj)
            
            files = self.get_files(outer)
            if self.allow_duplicate_file:
                self.sort_files(files, reverse=not self.page_ascending)
            await alist(amap(fn_files, files))
        
        await alist(amap(fn_outers, outers))
        return [
            self.file_name_todo(obj)
            for _, objs in self.folder_dic.values()
            for obj in objs
        ]

    async def remove_duplicate_files(self, outers: list[_OT]):
        hash_set = set()
        duplicate_count = 0
        all_count = 0
        
        if (self.reserve_latest_duplicate_file and self.serial_ascending) or \
            (not self.reserve_latest_duplicate_file and not self.serial_ascending):
            o_start = 0;             o_step = 1;  o_stop = len(outers)
        else:
            o_start = len(outers)-1; o_step = -1; o_stop = -1
        
        def fn_outers(index: int):
            
            def fn_files(index: int):
                nonlocal duplicate_count, all_count, offset
                if positive:
                    index += offset
                file = files[index]
                all_count += 1
                if (file_hash := self.get_file_hash(file)) in hash_set:
                    duplicate_count += 1
                    files.pop(index)
                    if positive:
                        offset -= 1
                else:
                    hash_set.add(file_hash)
            
            files = self.get_files(outers[index])
            if not files:
                return
            self.sort_files(files, not self.page_ascending)
            offset = 0
            if (self.reserve_latest_duplicate_file and self.page_ascending) or \
                (not self.reserve_latest_duplicate_file and not self.page_ascending):
                start = 0; step = 1; stop = len(files)
                positive = True
            else:
                start = len(files)-1; step = -1; stop = -1
                positive = False
            list(map(fn_files, range(start, stop, step)))
            
        list(map(fn_outers, range(o_start, o_stop, o_step)))
        if duplicate_count > 0:
            logger.info(f"Removed {duplicate_count}({duplicate_count/all_count:.2%}) duplicate files")
    
    def get_folder_actual(self, folder: str):
        parts = folder.split("/")
        new = f"{parts.pop()}_0{self.folder_count_dic[folder]}"
        return "/".join(parts) + "/" + new
    
    async def handle_serial_num(self, local: dict, outer: _OT, source: _ST, **kwargs) -> int:
        folder = kwargs["folder"]
        file_name = kwargs["file_name"]
        
        if folder in self.folder_count_dic:
            folder_actual = self.get_folder_actual(folder)
        else:
            folder_actual = folder
        local["folder_actual"] = folder_actual
        
        if self.enable_serial:
            if self.serial_type == "same_folder":
                serial_num = self.folder_dic[local["folder_actual"]][0]
                if self.max_single_folder_files > 0 and (serial_num.value >= self.max_single_folder_files + self.serial_start_num):
                    serial_num = self.handle_max_single_folder_files(local, outer, source, folder=folder, file_name=file_name)
                self.folder_dic[local["folder_actual"]][0] += 1
            else:
                serial_num = self.folder_dic["serial"][0]
                self.folder_dic["serial"][0] += 1
        else:
            serial_num = None
        return serial_num
    
    async def handle_page_num(self, local: dict, outer: _OT, source: _ST, **kwargs) -> int:
        if self.enable_page_num and (not self.page_num_include_types or 
            (self.page_num_include_types and local["file_type"] in self.page_num_include_types)):
            folder_postfix = self.get_page_based(local, outer, source, **kwargs)
            page_num = self.page_dic[folder_postfix][0] 
            self.page_dic[folder_postfix][0] += 1
        else:
            page_num = None
        return page_num

    def get_params(self):
        return {
            "root": self.root,
            "folder_expr": self.folder_coder.raw_code,
            "file_expr": self.file_coder.raw_code,
            "enable_serial": self.enable_serial,
            "serial_min_length": self.serial_min_length,
            "serial_type": self.serial_type,
            "serial_start_num": self.serial_start_num,
            "serial_ascending": self.serial_ascending,
            "min_serial_enable_count": self.min_serial_enable_count,
            "enable_page_num": self.enable_page_num,
            "page_num_min_length": self.page_num_min_length,
            "page_num_start": self.page_num_start,
            "page_num_include_types": self.page_num_include_types,
            "page_ascending": self.page_ascending,
            "min_page_enable_count": self.min_page_enable_count,
            "allow_duplicate_file": self.allow_duplicate_file,
            "reserve_latest_duplicate_file": self.reserve_latest_duplicate_file,
            "max_single_folder_files": self.max_single_folder_files,
            "keep_files_continuous": self.keep_files_continuous,
        }

