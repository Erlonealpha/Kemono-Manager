from random import randint
from typing import Optional
from PIL import Image
import os
from .tools import get_file_type_by_name

map_folder_by_type = {
    "img": "images",
    "gif": "gifs",
    "compress": "compress",
    "video": "videos",
    "audio": "audios",
    "psd": "psds",
    "doc": "docs",
    "code": "codes",
    "app": "apps",
    "other": "others",
    "unknown": "unknown"
}
def get_folder_by_filetype(type):
    rt = map_folder_by_type.get(type)
    if rt is None:
        return get_folder_by_filetype(get_file_type_by_name(type))
    return rt
def by_alpha_condition(file:str, title:str):
    def by_len():
        return file if len(file) < len(title) else title

    _file = file.replace('_', '').replace('-', '').lower()
    _title = title.replace('_', '').replace('-', '').lower()
    f = _file.isalnum()
    t = _title.isalnum()

    if f and not t:
        if len(file) < 24:
            return file
        else:
            return title
    elif not f and t:
        return file
    else:
        return by_len()
    
py_default_funcs = {
    'path_join': os.path.join,
    'path_dirname': os.path.dirname,
    'path_basename': os.path.basename,
    'path_splitext': os.path.splitext,
    'path_exists': os.path.exists,
    'path_isfile': os.path.isfile,
    'path_isdir': os.path.isdir,
    'path_listdir': os.listdir,
    
    # 'get_img_size': get_img_size,
    # 'get_type_from_name': get_type_from_name,
    # 'is_fanbox_cover': is_fanbox_cover,
    'get_folder_by_filetype': get_folder_by_filetype,
    'by_alpha_condition': by_alpha_condition
}



class RunCoder:
    def __init__(self, code:str, locals_vars:Optional[dict]=None):
        self.raw_code = code
        self.raw_locals = locals_vars
        self.pre_run()
    
    def run(self, **locals_vars):
        _locals_vars = locals_vars.copy()
        _locals_vars.update(self.local_vars)
        return _run_code(self.code, self.rt_name, _locals_vars)

    def pre_run(self):
        self.code, self.rt_name, self.local_vars = pre_run(self.raw_code, self.raw_locals)

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)

class ReturnVal:
    val = None
def get_first_indent(line:str):
    '''将有效的第一行的缩进作为需要去除的缩进'''
    space = 0
    if not line[0].isspace(): 
        return 0
    for char in line:
        if char == ' ': space += 1
        elif char == '\t': space += 4
        elif not char.isspace(): break
    return space
def strip_indent(line:str, space):
    '''去除缩进'''
    index = 0
    if space == 0: return line
    while space > 0:
        c = line[0]
        if c == ' ': space -= 1; index += 1
        elif c == '\t': space -= 4; index += 1
        else: break
    return line[index:]
def pre_code(code:str, rt_name, local_vars):
    '''将代码封装到main函数中'''
    # code = code.strip()
    func = 'main'
    while func in code or func in local_vars:
        func = 'main' + str(randint(10000000, 99999999))
    first_append_line = f'def {func}():\n'
    first = True
    for line in code.split('\n'):
        if line.strip() == '': continue
        if first:
            space = get_first_indent(line); first=False
        if locals().get('space') is None: 
            continue
        first_append_line += f'    {strip_indent(line, space)}\n'
    first_append_line += f'{rt_name}.val = {func}()\n'
    return first_append_line

def pre_run(code:str, local_vars):
    if 'return' not in code and '\n' not in code:
        code = "return " + code
    
    locs = py_default_funcs.copy()
    if local_vars is None: 
        local_vars = {}
    locs.update(local_vars)
    rt_name = 'rt_value'
    while rt_name in locs or rt_name in code:
        rt_name = 'rt_value' + str(randint(10000, 99999))
    rt_val = ReturnVal()
    # print(code)
    code = pre_code(code, rt_name, locs)
    # print(code)
    locs.update({rt_name: rt_val})
    return code, rt_name, locs

def run_code(code:str, local_vars:Optional[dict]):
    return _run_code(*pre_run(code, local_vars))
def _run_code(code, rt_name, locs):
    exec(code, locs)
    return locs[rt_name].val


if __name__ == '__main__':
    r = RunCoder("print(f'hello world', test)")
    for i in range(10):
        r.run({'test': i})
