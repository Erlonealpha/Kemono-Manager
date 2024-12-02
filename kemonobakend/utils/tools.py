from pathlib import Path
from hashlib import sha256, md5
from os import (
    fspath as os_fspath,
)
from os.path import (
    exists as path_exists, 
    join as path_join, 
    splitext as path_splitext,
    split as path_split
)
from aiofiles import open as aio_open
from json import load, dump, loads, dumps
import re

from typing import Union, Optional

from ua_generator import generate as ua_generate

UA_RAND = ua_generate()



class GenTaskID:
    def __init__(self):
        self._map = {}
        self._cache = {}
    
    def generate(self, name=None, start_value=0):
        if name is None:
            name = 'default'
        if name not in self._map:
            self._cache[name] = start_value
            self._map[name] = start_value
        task_id = self._map[name]
        self._map[name] += 1
        return task_id
    def reset(self):
        self._map = {}
    def reset_name(self, name, start_value=None):
        if name in self._map:
            self._map[name] = start_value or self._cache[name]

IdGenerator = GenTaskID()

def json_load(path: str, encoding='utf-8', **kwds) -> Optional[Union[dict, list]]:
    try:
        with open(path, 'r', encoding=encoding, **kwds) as f:
            return load(f)
    except (FileNotFoundError, ValueError):
        return None

def json_loads(s: str, **kwds) -> Optional[Union[dict, list]]:
    return loads(s, **kwds)

def json_dump(data, path: Union[str, Path], encoding='utf-8', ensure_ascii=False, indent=4, **kwds):
    if not isinstance(path, Path):
        path = Path(path)
    if not path.parent.exists():
        path.parent.mkdir(parents=True)
    with open(path, 'w', encoding=encoding) as f:
        dump(data, f, ensure_ascii=ensure_ascii, indent=indent, **kwds)

def json_dumps(data, ensure_ascii=False, **kwds):
    return dumps(data, ensure_ascii=ensure_ascii, **kwds)

def basename_part(path: str, part: int=2):
    '''选择保留多少个路径部分, 如果路径部分数小于part, 则返回原路径'''    
    if ('/' in path and '\\' in path) or ('/' not in path and '\\' in path):
        path = path.replace('\\', '/')
    path_parts = path.split('/')
    if len(path_parts) <= part:
        return path
    return '/'.join(path_parts[-part:])

type_map = {
    'img':      ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.ico', '.jpe'],
    'gif':      ['.gif'],
    'compress': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tar.gz', '.tar.bz2', '.tar.xz'],
    'video':    ['.mp4', '.avi', '.flv','.mkv', '.wmv', '.rmvb', '.webm'],
    'audio':    ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.opus'],
    'psd':      ['.psd'],
    'doc':      ['.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf', '.txt', '.epub'],
    'code':     ['.py', '.java', '.js', '.html', '.css', '.php', '.c', '.cpp', '.go', '.json', '.xml', '.yaml', '.yml'],
    'app':      ['.exe', '.app', '.apk', '.ipa'],
}

def get_file_type_by_name(path: str):
    '''根据文件扩展名获取文件类型'''
    if '.' not in path:
        return 'unknown'
    p = Path(path)
    for type_name, exts in type_map.items():
        if p.suffix in exts:
            return type_name
        elif len(p.suffixes) > 1:
            suffix = p.suffixes[-2]
            if suffix in exts and p.suffix.strip('.').isdigit():
                # eg. example.7z.001 -> compress
                return type_name
    return 'other'

def calc_file_sha256(path: str):
    '''计算文件的sha256值'''
    with open(path, 'rb') as f:
        sha256_obj = sha256()
        while True:
            data = f.read(65536)
            if not data:
                break
            sha256_obj.update(data)
        return sha256_obj.hexdigest()

async def async_calc_file_sha256(path: str):
    '''异步计算文件的sha256值'''
    async with aio_open(path, 'rb') as f:
        sha256_obj = sha256()
        while True:
            data = await f.read(65536)
            if not data:
                break
            sha256_obj.update(data)
        return sha256_obj.hexdigest()
    
def calc_str_sha256(s: str):
    '''计算字符串的sha256值'''
    sha256_obj = sha256()
    sha256_obj.update(s.encode('utf-8'))
    return sha256_obj.hexdigest()

def calc_str_md5(s: str):
    '''计算字符串的md5值'''
    md5_obj = md5()
    md5_obj.update(s.encode('utf-8'))
    return md5_obj.hexdigest()

def verify_file_sha256(path: str, sha256_value: str, strict=False):
    '''验证文件的sha256值'''
    if not path_exists(path) or not sha256_value:
        return not strict
    return calc_file_sha256(path) == sha256_value

async def async_verify_file_sha256(path: str, sha256_value: str, strict=False):
    '''异步验证文件的sha256值'''
    if not path_exists(path) or not sha256_value:
        return not strict
    return await async_calc_file_sha256(path) == sha256_value

Units = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
mach_re = re.compile(r"(\d+(\.\d+)?)([KMGTPEZY]?B)")
def get_num_and_unit(num: str) -> str:
    num = num.upper()
    match_obj = re.match(mach_re, num)
    if match_obj is not None:
        num = int(match_obj.group(1))
        unit = match_obj.group(3)
    else:
        num = int(num)
        unit = "B"
    return num, unit
def to_bytes(num: Union[str, int], unit: Optional[str] = None):
    # 根据后缀，转换为字节数
    if unit is not None:
        unit = unit.upper()
        num = int(num)
    else:
        num, unit = get_num_and_unit(num)
    unit = Units.index(unit)
    return num * 1024 ** unit
def to_unit(num: Optional[int], unit: Optional[str]=None, precision: int=2, keep_length:Optional[int] = None) -> str:
    # 根据字节数，转换为后缀
    if num is None:
        if keep_length is not None and keep_length > 3:
            return "N/A".rjust(keep_length + 2)
        return "N/A"
    unit_idx = Units.index(unit) if unit is not None else 8
    if not unit:
        for i in range(unit_idx, -1, -1):
            if num >= 1024 ** i or i == 0:
                num = num/1024**i
                unit = Units[i]
                break
    else:
        unit = unit.upper()
        num = num/1024**unit_idx
        if 0 < num < 1:
            c = count_leading_zeros_after_decimal(num)
            precision = c + precision
    
    num_str = f"{num:.{precision}f}"
    l = len(num_str) - 1 if '.' in num_str else len(num_str)
    if keep_length and keep_length is not None and l < keep_length:
        num_str_z_len = len(num_str.split('.')[0]) if '.' in num_str else len(num_str)
        precision = keep_length - num_str_z_len
        num_str = f"{num:.{precision}f}"
        if len(num_str) - 1 if '.' in num_str else len(num_str) < keep_length:
            num_str = num_str.ljust(keep_length+1, '0') if '.' in num_str else num_str.ljust(keep_length, '0')

    return f"{num_str}{unit}"
def count_leading_zeros_after_decimal(number):
    # 确保输入的数小于1
    if number >= 1 or number <= 0:
        raise ValueError("输入的数必须小于1且大于0")
    
    # 计算小数部分有多少个连续的0
    count = 0
    while number < 1:
        number *= 10
        if number < 1:
            count += 1
        else:
            break
    
    return count

def sanitize_windows_path(path):
    # '\t\n\r\a\f\v' 表示的字符
    control_chars = ''.join(map(chr, range(0, 32)))  # 包含所有控制字符
    return re.sub(f'[{re.escape(control_chars)}<>:"/\\|?*]', '', path)

if __name__ == '__main__':
    print(sanitize_windows_path(""))