from rich import print

from os.path import join as _join
from os.path import dirname as _dirname
from os.path import basename as _basename
from os.path import exists as _exists
from os.path import isfile as _isfile
from os.path import isdir as _isdir
from pathlib import Path
from subprocess import run as subprocess_run, PIPE
from sys import platform, getfilesystemencoding
import ctypes

from typing import TypeAlias, Literal

encodings = ["utf-8", "gbk", "gb2312", "big5"] # ...

mklinkType: TypeAlias = Literal['D', 'H', 'J']

dwFlagsType: TypeAlias = Literal[
    0x0, # The link target is a file.
    0x1, # The link target is a directory.
    0x2  # Specify this flag to allow creation of symbolic links when the process is not elevated. 
]        # Developer Mode must first be enabled on the machine before this option will function.

g_mk_link_instance = None
class MKLinkMeta(type):
    def __call__(cls, *args, **kwargs):
        global g_mk_link_instance
        if g_mk_link_instance is not None:
            return g_mk_link_instance
        g_mk_link_instance = type.__call__(cls, *args, **kwargs)
        return g_mk_link_instance
class MKLink(metaclass=MKLinkMeta):
    
    def __init__(self):
        self.dll = ctypes.windll.LoadLibrary("kernel32.dll")
        self.dll.CreateSymbolicLinkW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
        self.dll.CreateHardLinkW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
    
    def _CreateSymbolicLinkW(self, targetFile: str, linkFile: str, flags: dwFlagsType) -> int:
        return self.dll.CreateSymbolicLinkW(targetFile, linkFile, flags)

    def _CreateHardLinkW(self, targetFile: str, existingFile: str, securityAttributes) -> int:
        return self.dll.CreateHardLinkW(targetFile, existingFile, securityAttributes)

    @staticmethod
    def _handle_file_existence(file: Path, existing_file: Path, flags=None):
        if file.exists():
            raise FileExistsError(f"Target path {file} already exists.")
        if flags is not None:
            if flags == 0 and not existing_file.is_file():
                raise Exception(f"Source path {existing_file} is not a file.")
            elif flags == 1 and not existing_file.is_dir():
                raise Exception(f"Source path {existing_file} is not a directory.")
    
    def _create_symbolic_link(self, file: Path, existing_file: Path, flags: dwFlagsType) -> bool:
        try:
            MKLink._handle_file_existence(file, existing_file, flags)
            ret = self._CreateSymbolicLinkW(str(file), str(existing_file), flags)
            if not ret:
                exc = ctypes.WinError() # get the last error
                raise OSError(f"Failed to create symbolic link: {existing_file} -> {file} ({exc})")
            return True
        except Exception as e:
            raise e
    
    def _create_hard_link(self, file: Path, existing_file: Path, security_attributes):
        try:
            MKLink._handle_file_existence(file, existing_file)
            ret = self._CreateHardLinkW(str(file), str(existing_file), security_attributes)
            if not ret:
                exc = ctypes.WinError()
                raise OSError(f"Failed to create hard link: {existing_file} -> {file} ({exc})")
            return True
        except Exception as e:
            raise e

    @staticmethod
    def _get_cls():
        global g_mk_link_instance
        if g_mk_link_instance is None:
            g_mk_link_instance = MKLink()
        return g_mk_link_instance

    @staticmethod
    def _mklink(file, existing_file, mode:mklinkType='D'):
        if not isinstance(file, Path):
            file = Path(file)
        if not isinstance(existing_file, Path):
            existing_file = Path(existing_file)
        if not existing_file.exists():
            raise FileNotFoundError(f"Source path {existing_file} does not exist.")
        if not file.parent.exists():
            file.parent.mkdir(parents=True)
        cls = MKLink._get_cls()
        match mode.lower():
            case 'd':
                return cls._create_symbolic_link(file, existing_file, 1)
            case 'h':
                return cls._create_hard_link(file, existing_file, 0)
            case 'j':
                return cls._create_symbolic_link(file, existing_file, 0)
            case _:
                raise ValueError(f"Invalid mode: {mode}")
            
    @staticmethod
    def create_symbolic_link(file:str, existing_file:str):
        return MKLink._mklink(file, existing_file, 'D')
    @staticmethod
    def create_hard_link(file:str, existing_file:str):
        return MKLink._mklink(file, existing_file, 'H')
    @staticmethod
    def create_junction_link(file:str, existing_file:str):
        return MKLink._mklink(file, existing_file, 'J')
    
    @staticmethod
    def mk_link_cmd(existing_file, file, mode:mklinkType=""):
        if platform == "win32":
            cmd = f'mklink /{mode} "{file}" "{existing_file}"'
            p = subprocess_run(cmd, shell=True, stdout=PIPE, stderr=PIPE)
            encoding = getfilesystemencoding()
            if encoding not in encodings:
                encodings.insert(0, encoding)
            for encoding in encodings:
                try:
                    stdout = p.stdout.decode(encoding)
                    stderr = p.stderr.decode(encoding)
                    break
                except UnicodeDecodeError:
                    pass
            else:
                raise UnicodeDecodeError("Failed to decode output")

            if p.returncode!= 0 or stderr:
                print(f"[red]Error: {stderr}[/red]")
            else:
                print(f"[green]{stdout}[/green]")
        else:
            raise NotImplementedError("Not implemented for non-windows platform")



if __name__ == '__main__':
    target_folder = r'F:\图片\patreon\houkisei\folder\wait_for_merge'
    # target_folder= [r'F:\图片\patreon\houkisei\folder\2024.7', r'F:\图片\patreon\houkisei\folder\2024.8', r'F:\图片\patreon\houkisei\folder\2024.9']
    copy_folder = r"F:\图片\patreon\houkisei\folder\2024.9"
    copy_folder2 = r'G:\YOL\图片\按作者\houk1se1'
    # copy_folder2 = r'G:\YOL\Kemono\KemonoManager\fanbox\ドシーロ\ehone'
    # merge_to_one_with_empty(target_folder, copy_folder, no_page=False, folder_ascending=False, file_ascending=True, start_count=1, page_start=1)
    # merge_to_one_v2(target_folder, copy_folder2, folder_ascending=False)
    # T_fill_zero(copy_folder2)
    e_f = "G:\\YOL\\Kemono\\KemonoManager\\patreon\\houkisei\\images\\0001_1_1.jpg"
    f = "G:\\YOL\\Kemono\\KemonoManager\\patreon\\houkisei\\test.jpg"
    e_f = "G:/YOL/Kemono/Resource/0a/5f/0a5f10e65dda15729de5001355baf0506973487726d79aed8af4ed6eb2338aa9"
    f = "G:/YOL/Kemono/20241004.zip"
    cls = MKLink()
    MKLink.create_hard_link(f, e_f)
    # if _exists(e_f):
        # win32file.CreateHardLink(e_f, f)
        # MKLink.mk_link_cmd(e_f, f)
