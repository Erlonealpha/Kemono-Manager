from zipfile import ZipFile
from .base import FilesFormatterBase



class CompressFormatter(FilesFormatterBase):
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
        page_num_include_types: list[str] = ..., 
        page_ascending: bool = True, 
        min_page_enable_count: int = 2, 
        allow_duplicate_file: bool = False, 
        reserve_latest_duplicate_file: bool = True, 
        max_single_folder_files: int = 2000, 
        keep_files_continuous: bool = True
    ):
        super().__init__(formatter_name, root, folder_expr, file_expr, enable_serial, serial_min_length, serial_type, serial_start_num, serial_ascending, min_serial_enable_count, enable_page_num, page_num_min_length, page_num_start, page_num_include_types, page_ascending, min_page_enable_count, allow_duplicate_file, reserve_latest_duplicate_file, max_single_folder_files, keep_files_continuous)