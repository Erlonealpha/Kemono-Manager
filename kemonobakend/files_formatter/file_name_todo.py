from typing import Union, Coroutine, Type, TypeVar, Any

from kemonobakend.kemono.builtins import format_name
from kemonobakend.utils import path_splitext
from kemonobakend.log import logger

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
        # !! Why self.min_enable_count + 1? 
        # !! In case of the last added value is not used.
        # !! If we change the counting logic of value, it will increase each time the value is used, 
        # !! and we can remove this +1.
        if self.total.value < self.min_enable_count + 1:
            return "" 
        else:
            raw_str = str(self.value)
            fill_len = len(str(self.total.value))
            if fill_len < self.min_length:
                fill_len = self.min_length
            return raw_str.zfill(fill_len)
    
    def __repr__(self):
        return f"NumWithZFiller({self.__str__()}, total={self.total.value})"