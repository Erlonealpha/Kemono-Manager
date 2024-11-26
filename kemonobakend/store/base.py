from pathlib import Path
from functools import cached_property
from pickle import load as pickle_load, dump as pickle_dump
from typing import Optional, Union

from kemonobakend.utils import path_join
from kemonobakend.log import logger


class StoreBase:
    def __init__(self):
        self.init = False
    
    def _init(self):
        self.init = True
        self.load()
    
    @cached_property
    def _path(self):
        return Path(path_join("data", "stores", self.__class__.__name__.lower() + '.json'))
    
    def load(self):
        if not self._path.exists():
            return None
        data = pickle_load(self._path)
        return data
    
    def dump(self, data):
        if data is not None:
            try:
                pickle_dump(data, self._path)
            except Exception as e:
                logger.exception(e)
    
    def __del__(self):
        self.dump(None)
