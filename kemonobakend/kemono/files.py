from collections import defaultdict
from typing import Union, Coroutine, Type, TypeVar, Any

from kemonobakend.files_formatter import FilesFormatterBase, FileNameZFillerToDo, NumWithZFiller
from kemonobakend.database.models import KemonoAttachment, KemonoUser, KemonoPost, KemonoFile
from kemonobakend.database.model_builder import build_kemono_file_by_attachment
from kemonobakend.utils import (
    os_fspath, path_join, path_splitext, path_exists, 
    sanitize_windows_path, get_file_type_by_name
)
from kemonobakend.utils.run_code import RunCoder, get_first_indent
from kemonobakend.log import logger


class KemonoFilesFormatter(FilesFormatterBase):
    __return_class__: Type[KemonoFile] = KemonoFile

    @staticmethod
    def default_folder_expr() -> str:
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

    @staticmethod
    def default_file_expr() -> str:
        return \
        '''
        f, ext = path_splitext(attachment.name)
        return by_alpha_condition(f, post.title) + ext
        '''

    def with_default_folder_expr(self, exprs: list[tuple[str, str]]):
        '''
        Inputs: 
            exprs: list of tuples, where each tuple contains a condition and a folder name.
        Example:
        ```python
        >>> input = [("'XXXX' in attachment.title", "XXXX")]
        # it will add the following code to the folder expression:
        elif 'XXXX' in attachment.title:
            folder = 'XXXX'
        ```
        '''
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
        for condition, folder in exprs:
            lines.insert(insert_pos, f"{spaces}elif {condition}:")
            # !!default 4 spaces per indent!!
            lines.insert(insert_pos+1, f"{spaces}    folder = {folder}")
            insert_pos += 2

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
        if self.keep_files_continuous:
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
