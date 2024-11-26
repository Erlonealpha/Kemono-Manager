import os
import shutil
from pathlib import Path
from kemonobakend.utils import verify_file_sha256, async_verify_file_sha256, async_calc_file_sha256, calc_file_sha256

class ResourceHandler:
    def __init__(self, root: str):
        self.root = root
    
    def get_path(self, sha256, hash_id = None):
        if sha256 is None:
            path = os.path.join(self.root, "no_hash", hash_id)
        else:
            path = os.path.join(self.root, sha256[:2] ,sha256[2:4], sha256)
        return Path(path)
    
    def get_tmp_path(self, sha256):
        return Path(os.path.join(self.root, "tmp", sha256))
    
    def exists(self, sha256, hash_id = None):
        path = self.get_path(sha256, hash_id)
        return os.path.exists(path)
    
    def get_all_resources(self):
        all_files = []
        for root, dirs, files in os.walk(self.root):
            if root.split(os.sep)[-1] == "no_hash":
                no_hash_files = [os.path.join(root, file) for file in files]
            all_files.extend([os.path.join(root, file) for file in files])
        return all_files, no_hash_files
    
    def remove(self, sha256, hash_id = None):
        path = self.get_path(sha256, hash_id)
        if path.exists():
            path.unlink()
    
    def get_file_hash(self, sha256):
        path = self.get_path(sha256)
        if path.exists():
            return calc_file_sha256(path)
    
    async def async_get_file_hash(self, sha256):
        path = self.get_path(sha256)
        if os.path.exists(path):
            return await async_calc_file_sha256(path)
    
    def verify_file(self, sha256):
        path = self.get_path(sha256)
        return verify_file_sha256(path, sha256, True)

    async def async_verify_file(self, sha256):
        path = self.get_path(sha256)
        return await async_verify_file_sha256(path, sha256, True)
    
    def move_to_tmp(self, sha256):
        path = self.get_path(sha256)
        tmp_path = Path(os.path.join(self.root, "tmp", sha256))
        if not tmp_path.parent.exists():
            tmp_path.parent.mkdir(parents=True)
        shutil.move(path, tmp_path)