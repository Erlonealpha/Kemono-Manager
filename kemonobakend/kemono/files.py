from pathlib import Path
from collections import defaultdict
from abc import ABC, abstractmethod

from typing import Union, Coroutine, Type, TypeVar, Any
from asyncstdlib.builtins import map as amap, list as alist

from kemonobakend.database.models import KemonoAttachment, KemonoUser, KemonoPost, KemonoFile
from kemonobakend.database.model_builder import build_kemono_file_by_attachment
from kemonobakend.api import KemonoAPI
from kemonobakend.log import logger
from kemonobakend.kemono.builtins import format_name
from kemonobakend.utils import (
    os_fspath, path_join, path_splitext, path_exists, 
    sanitize_windows_path, get_file_type_by_name
)
from kemonobakend.utils.run_code import RunCoder, get_first_indent
from kemonobakend.utils.progress import NormalProgress
from kemonobakend.utils.mklink import MKLink

from .resource_handler import ResourceHandler


def remove_duplicate_files(posts: list[KemonoPost], reserve_latest: bool = True):
    sha256_set = set()
    duplicate_count = 0
    if reserve_latest:
        p_start = 0;             p_step = 1;  p_stop = len(posts)
    else:
        p_start = len(posts)-1;  p_step = -1; p_stop = -1
    for i in range(p_start, p_stop, p_step):
        for j in range(len(posts[i].attachments)-1, -1, -1):
            if posts[i].attachments[j].sha256 in sha256_set:
                posts[i].attachments.pop(j)
                duplicate_count += 1
            else:
                sha256_set.add(posts[i].attachments[j].sha256)
    if duplicate_count > 0:
        logger.info(f"Removed {duplicate_count} duplicate files")

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
    
    # @staticmethod
    # @abstractmethod
    # def get_folder_dic() -> defaultdict[str, tuple['NumWithZFiller', list[_ST]]]: ...
    
    # @staticmethod
    # @abstractmethod
    # def get_page_dic() -> defaultdict[str, tuple['NumWithZFiller', list[_ST]]]: ...

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
        min_serial_enable_count: int = 1,
        enable_page_num: bool = True,
        page_num_min_length: int = 2,
        page_num_start: int = 1,
        page_num_include_types: list[str] = ["img", "video"],
        page_ascending: bool = True,
        min_page_enable_count: int = 1,
        allow_duplicate_file: bool = False,
        reserve_latest_duplicate_file: bool = True,
        max_single_folder_files: int = 2000,
    ):
        self.formatter_name = formatter_name
        self.root = root.replace("\\", "/")
        self.folder_coder = RunCoder(folder_expr)
        self.file_coder = RunCoder(file_expr)
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
                if serial_num.value >= self.max_single_folder_files + self.serial_start_num:
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
        }



class KemonoFilesFormatter(FilesFormatterBase):
    __return_class__ = KemonoFile
    __source_iterative_layer__ = 2
    
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
        min_serial_enable_count: int = 1,
        enable_page_num: bool = True,
        page_num_min_length: int = 2,
        page_num_start: int = 1,
        page_num_include_types: list[str] = ["img", "video"],
        page_ascending: bool = True,
        min_page_enable_count: int = 1,
        allow_duplicate_file: bool = False,
        reserve_latest_duplicate_file: bool = True,
        max_single_folder_files: int = 2000,
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

    def default_folder_expr(self) -> str:
        return \
        '''
        base_dir = path_join(creator.public_name, creator.service)
        if attachment.type == "cover":
            folder = "cover"
        elif attachment.type == "thumbnail":
            folder = "thumbnail"
        else:
            folder = get_folder_by_filetype(file_type)
        return path_join(base_dir, folder)
        '''
    
    def default_file_expr(self) -> str:
        return \
        '''
        f, ext = path_splitext(attachment.name)
        return by_alpha_condition(f, post.title) + ext
        '''

    def with_default_folder_expr(self, exprs: list[str]):
        '''
        the input exprs should be a list of string, each string is a comma-separated expression,
        eg.
        ```
        # input = ["'XXXX' in attachment.title,'XXXX'"]
        # ->
        elif 'XXXX' in attachment.title:
            folder = 'XXXX'
        ```
        '''
        def split_expr(expr: str) -> tuple[str, str]:
            s = expr[-1]
            start_search_pos = None
            for i in range(len(expr)-2, -1, -1):
                if expr[i] == s:
                    start_search_pos = i
                if start_search_pos is not None and expr[i] == ',':
                    return expr[:i].strip(), expr[i+1:].strip()
        
        exprs = [split_expr(expr) for expr in exprs]
        folder_expr = self.default_folder_expr()
        
        lines = [e for e in folder_expr.splitlines() if e.strip()]
        indent = get_first_indent(lines[0])
        spaces = " " * indent
        for i in range(len(lines)):
            if lines[i].strip().startswith("else:"):
                insert_pos = i
                break
        else:
            insert_pos = len(lines)
        for expr in exprs:
            if len(expr) == 2:
                condition, folder = expr
                lines.insert(insert_pos, f"{spaces}elif {condition}:")
                # !!default 4 spaces per indent!!
                lines.insert(insert_pos+1, f"{spaces}    folder = {folder}")
                insert_pos += 2
            else:
                raise ValueError("Invalid expression, Must be in format of 'condition,folder'")
        self.folder_coder.raw_code = "\n".join(lines)
        self.folder_coder.pre_run() # update the compiled code
        return self
    
    def with_default_file_expr(self, exprs: list[str]):
        pass
    
    def get_files(self, outer: KemonoPost) -> list[KemonoFile]:
        return outer.attachments
    
    def get_file_hash(self, file: KemonoFile) -> str:
        return file.sha256
    
    def sort_outers(self, outers: list[KemonoPost]):
        try:
            if outers[0].post_id.isdigit():
                outers.sort(key=lambda x: int(x.post_id), reverse=self.serial_ascending)
            else:
                outers.sort(key=lambda x: x.published, reverse=not self.serial_ascending)
        except Exception as e:
            logger.warning(f"Failed to sort posts: {e}")
            pass
    
    def sort_files(self, files: list[KemonoFile], reverse: bool = False):
        try:
            files.sort(key=lambda x: x.idx, reverse=reverse)
        except Exception as e:
            logger.warning(f"Failed to sort files: {e}")
            pass
    
    async def format_folder_and_file_name(self, local: dict, post: KemonoPost, attachment: KemonoAttachment, creator: KemonoUser, **kwd) -> str:
        file_type = get_file_type_by_name(attachment.name)
        local["file_type"] = file_type
        
        try:
            attachment = attachment.model_copy()
            creator = creator.model_copy()
            post = post.model_copy()
            creator.name = sanitize_windows_path(creator.name)
            attachment.name = sanitize_windows_path(attachment.name)
            post.title = sanitize_windows_path(post.title)
        except:
            creator.name = sanitize_windows_path(creator.name)
            attachment.name = sanitize_windows_path(attachment.name)
            post.title = sanitize_windows_path(post.title)
        
        folder: str = self.folder_coder.run(root=self.root, file_type=file_type, creator=creator, post=post, attachment=attachment)
        file_name: str = sanitize_windows_path(self.file_coder.run(root=self.root, file_type=file_type, creator=creator, post=post, attachment=attachment))

        if not isinstance(folder, str) or not isinstance(file_name, str):
                    raise ValueError("Folder or file name expression return non-string value")
        
        folder = folder.replace("\\", "/")
        return folder, file_name

    def handle_max_single_folder_files(self, local: dict, post: KemonoPost, attachment: KemonoAttachment, **kwargs) -> int:
        folder = kwargs["folder"]
        
        if folder not in self.folder_count_dic:
            self.folder_count_dic[folder] = 1
        else:
            self.folder_count_dic[folder] += 1
        
        # 为了保证在达到文件夹最大文件数时，同一post的附件是连续的
        # 需要向前查找直到找到第一个post_hash_id不等于当前post_hash_id的文件
        # 移动了之后还需要重新排序和重新计数页面
        kemono_files = self.folder_dic[local["folder_actual"]][1]
        need_ahead_files: list[KemonoFile] = []
        for i in range(len(kemono_files) - 1, -1, -1):
            if kemono_files[i].post_hash_id != attachment.post_hash_id:
                break
            need_ahead_files.insert(0, kemono_files.pop())
        # 覆盖folder_actual的位置不能出错
        if need_ahead_files:
            need_ahead_files[0].file_name.serial.total -= len(need_ahead_files)
            self.folder_dic[local["folder_actual"]][0].value -= len(need_ahead_files)
        local["folder_actual"] = self.get_folder_actual(folder)
        
        for i, kemono_file in enumerate(need_ahead_files):
            kemono_file.folder = local["folder_actual"]
            file_name: FileNameZFillerToDo = kemono_file.file_name
            file_name.serial = self.folder_dic[local["folder_actual"]][0]
            self.folder_dic[local["folder_actual"]][0] += 1
            self.folder_dic[local["folder_actual"]][1].append(kemono_file)
        serial_num = self.folder_dic[local["folder_actual"]][0]
        return serial_num
    
    def get_page_based(self, local: dict, post: KemonoPost, attachment: KemonoAttachment, **kwargs) -> str:
        return f"{local["folder_actual"]}_{attachment.post_hash_id}"

    def build_return_object(self, local: dict, post: KemonoPost, attachment: KemonoAttachment, file_name_zfiller: "FileNameZFillerToDo", **kwargs) -> KemonoFile:
        return build_kemono_file_by_attachment(self.formatter_name, attachment, None, self.root, local["folder_actual"], file_name_zfiller, file_type=local["file_type"])
    
    def file_name_todo(self, kemono_file: KemonoFile):
        kemono_file.file_name = str(kemono_file.file_name)
        kemono_file.save_path = path_join(self.root, kemono_file.folder, kemono_file.file_name)
        return kemono_file
    
    async def generate_files(self, creator: KemonoUser, posts: list[KemonoPost]):
        return await super().generate_files(posts, creator=creator)
    
    async def generate_files_o(self, creator: KemonoUser, posts: list[KemonoPost]):
        def init_folder_dic_item(start_num, min_enable_count, min_length):
            return [NumWithZFiller(start_num, min_enable_count, min_length), []]
        
        def get_folder_actual(folder: str):
            parts = folder.split("/")
            new = f"{parts.pop()}_0{folder_count_dic[folder]}"
            return "/".join(parts) + "/" + new
        
        if not posts:
            return []
        folder_count_dic: dict[str, int] = defaultdict(int)
        folder_dic: dict[str, tuple[NumWithZFiller, list[KemonoFile]]] = defaultdict(
            lambda: init_folder_dic_item(self.serial_start_num, self.min_serial_enable_count, self.serial_min_length))
        page_dic: dict[str, tuple[NumWithZFiller, list[KemonoFile]]] = defaultdict(
            lambda: init_folder_dic_item(self.page_num_start, self.min_page_enable_count, self.page_num_min_length))
        try:
            if posts[0].post_id.isdigit():
                posts.sort(key=lambda x: int(x.post_id), reverse = self.serial_ascending)
            else:
                posts.sort(key=lambda x: x.published, reverse = not self.serial_ascending)
        except:
            pass
        if not self.allow_duplicate_file:
            sha256_set = set()
            duplicate_count = 0
            if self.reserve_latest_duplicate_file:
                p_start = 0;             p_step = 1;  p_stop = len(posts)
            else:
                p_start = len(posts)-1;  p_step = -1; p_stop = -1
            for i in range(p_start, p_stop, p_step):
                if self.reserve_latest_duplicate_file:
                    reverse = not self.page_ascending
                else:
                    reverse = self.page_ascending
                posts[i].attachments.sort(key=lambda x: x.idx, reverse = reverse)
                for j in range(len(posts[i].attachments)-1, -1, -1):
                    if posts[i].attachments[j].sha256 in sha256_set:
                        posts[i].attachments.pop(j)
                        duplicate_count += 1
                    else:
                        sha256_set.add(posts[i].attachments[j].sha256)
                if not self.reserve_latest_duplicate_file:
                    posts[i].attachments.sort(key=lambda x: x.idx, reverse = not reverse)
            if duplicate_count > 0:
                logger.info(f"Removed {duplicate_count} duplicate files")

        for post in posts:
            if self.allow_duplicate_file:
                post.attachments.sort(key=lambda x: x.idx, reverse = not self.page_ascending)
            for attachment in post.attachments:
                try:
                    _ = attachment.post.post_id
                except:
                    attachment.post = post
                file_type = get_file_type_by_name(attachment.name)
                
                # 对于所有与生成文件路径的相关变量，都需要进行转义，防止路径中含有特殊字符
                try:
                    attachment = attachment.model_copy()
                    creator = creator.model_copy()
                    creator.name = sanitize_windows_path(creator.name)
                    attachment.name = sanitize_windows_path(attachment.name)
                    attachment.post.title = sanitize_windows_path(attachment.post.title)
                except:
                    creator.name = sanitize_windows_path(creator.name)
                    attachment.name = sanitize_windows_path(attachment.name)
                    attachment.post.title = sanitize_windows_path(attachment.post.title)
                
                folder: str = self.folder_coder.run(root=self.root, file_type=file_type, creator=creator, attachment=attachment)
                file_name: str = sanitize_windows_path(self.file_coder.run(root=self.root, file_type=file_type, creator=creator, attachment=attachment))
                
                if not isinstance(folder, str) or not isinstance(file_name, str):
                    raise ValueError("Folder or file name expression return non-string value")
                
                folder = folder.replace("\\", "/")
                if folder in folder_count_dic:
                    folder_actual = get_folder_actual(folder)
                else:
                    folder_actual = folder
                
                if self.enable_serial:
                    if self.serial_type == "same_folder":
                        # if folder_actual not in folder_dic:
                        #     folder_dic[folder_actual] = init_folder_dic_item(self.serial_start_num, self.min_serial_enable_count)
                        serial_num = folder_dic[folder_actual][0]
                        
                        if serial_num.value >= self.max_single_folder_files + self.serial_start_num:
                            if folder not in folder_count_dic:
                                folder_count_dic[folder] = 1
                            else:
                                folder_count_dic[folder] += 1
                            
                            # 为了保证在达到文件夹最大文件数时，同一post的附件是连续的
                            # 需要向前查找直到找到第一个post_hash_id不等于当前post_hash_id的文件
                            # 移动了之后还需要重新排序和重新计数页面
                            kemono_files = folder_dic[folder_actual][1]
                            need_ahead_files: list[KemonoFile] = []
                            for i in range(len(kemono_files) - 1, -1, -1):
                                if kemono_files[i].post_hash_id != attachment.post_hash_id:
                                    break
                                need_ahead_files.insert(0, kemono_files.pop())
                            # 覆盖folder_actual的位置不能出错
                            folder_actual = get_folder_actual(folder)
                            if need_ahead_files:
                                folder_dic[folder_actual] = init_folder_dic_item(self.serial_start_num, self.min_serial_enable_count, self.serial_min_length)
                                need_ahead_files[0].file_name.serial.total -= len(need_ahead_files)
                            for i, kemono_file in enumerate(need_ahead_files):
                                file_name: FileNameZFillerToDo = kemono_file.file_name
                                file_name.serial = folder_dic[folder_actual][0]
                                folder_dic[folder_actual][0] += 1
                                folder_dic[folder_actual][1].append(kemono_file)
                            serial_num = folder_dic[folder_actual][0]
                        folder_dic[folder_actual][0] += 1
                    else:
                        # if "serial" not in folder_dic:
                        #     folder_dic["serial"] = init_folder_dic_item(self.serial_start_num, self.min_serial_enable_count)
                        serial_num = folder_dic["serial"][0]
                        folder_dic["serial"][0] += 1
                else:
                    serial_num = None
                
                if self.enable_page_num and (not self.page_num_include_types or 
                    (self.page_num_include_types and file_type in self.page_num_include_types)):
                    folder_postfix = f"{folder_actual}_{attachment.post_hash_id}"
                    # if folder_postfix not in page_dic:
                    #     page_dic[folder_postfix] = init_folder_dic_item(self.page_num_start, self.min_page_enable_count)
                    page_num = page_dic[folder_postfix][0]
                    page_dic[folder_postfix][0] += 1
                else:
                    page_num = None
                
                file_name_zfiller = FileNameZFillerToDo(
                    file_name,
                    serial_num,
                    page_num
                )
                
                kemono_file = build_kemono_file_by_attachment(self.formatter_name, attachment, None, self.root, folder_actual, file_name_zfiller, file_type=file_type)
                folder_dic[folder_actual][1].append(kemono_file)
        
        def file_name_todo(kemono_file: KemonoFile):
            kemono_file.file_name = str(kemono_file.file_name)
            kemono_file.save_path = path_join(self.root, kemono_file.folder, kemono_file.file_name)
            return kemono_file
        
        all_kemono_files = [
            file_name_todo(kemono_file)
            for _, kemono_files in folder_dic.values()
            for kemono_file in kemono_files
        ]
        return all_kemono_files

class FileNameZFillerToDo:
    def __init__(self, file_name: str, serial: 'NumWithZFiller', page: 'NumWithZFiller'):
        self.file_name = file_name
        self.serial = serial
        self.page = page
    
    def __str__(self):
        f, ext = path_splitext(self.file_name)
        f = format_name(f)
        if len(ext) > 32:
            ext = ext[:32]
        serial_str = str(self.serial) + "_" if self.serial is not None else ""
        page_str = "_" + str(self.page) if self.page is not None else ""
        return f"{serial_str}{f}{page_str}{ext}"
    
    def __repr__(self):
        return f"FileNameZFillerToDo({self.__str__()}, serial={self.serial}, page={self.page})"

class _total:
    def __init__(self, value: int = 0):
        self.value = value
    def __add__(self, other: '_total'):
        if isinstance(other, int):
            self.value += other
        else:
            self.value += other.value
        return self
    def __sub__(self, other: '_total'):
        if isinstance(other, int):
            self.value -= other
        else:
            self.value -= other.value
        return self
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return f"_total({self.value})"
class NumWithZFiller:
    def __init__(self, value: int = 0, min_enable_count = 1, min_length=1, *, total=None):
        self.value = value
        self.total = total or _total(value)
        self.min_enable_count = min_enable_count
        self.min_length = min_length
    def __add__(self, other: int):
        self.total += other
        return self.only_add(other)
    def __sub__(self, other: int):
        self.total -= other
        return self.only_sub(other)
    def only_add(self, other: int):
        other_ = NumWithZFiller(self.value, self.min_enable_count, total=self.total)
        other_.value += other
        return other_
    def only_sub(self, other: int):
        other_ = NumWithZFiller(self.value, self.min_enable_count, total=self.total)
        other_.value -= other
        return other_
    
    def __str__(self):
        if self.total.value <= self.min_enable_count + 1:
            return ""
        else:
            raw_str = str(self.value)
            fill_len = len(str(self.total.value))
            if fill_len < self.min_length:
                fill_len = self.min_length
            return raw_str.zfill(fill_len)
    
    def __repr__(self):
        return f"NumWithZFiller({self.__str__()}, total={self.total.value})"


async def hard_link_files(res_root: str, kemono_files: list[KemonoFile]):
    hard_link_map = {}
    res_handler = ResourceHandler(res_root)
    for kemono_file in kemono_files:
        res_path = res_handler.get_path(kemono_file.sha256, kemono_file.attachment_hash_id)
        if not path_exists(res_path):
            logger.warning(f"File {res_path} not exists, skip hard link")
            continue
        elif path_exists(kemono_file.save_path):
            logger.warning(f"File {kemono_file.save_path} already exists, skip hard link")
            continue
        else:
            hard_link_map[kemono_file.save_path] = res_path
    
    with NormalProgress() as progress:
        task = progress.add_task("Hard Linking", total=len(hard_link_map))
        for target, rel in hard_link_map.items():
            try:
                MKLink.create_hard_link(target, rel)
            except Exception as e:
                logger.error(f"Failed to hard link {rel} -> {target}, {e}")
            finally:
                task.advance()
