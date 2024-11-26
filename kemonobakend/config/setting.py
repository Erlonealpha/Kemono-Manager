from pydantic import BaseModel, Field
from pathlib import Path

from .config import (
    ProgramConfig,
    ProxiesConfig,
    SessionPoolConfig,
    KemonoAPIConfig,
    DownloadConfig
)
from kemonobakend.utils import json_load, json_dump

CONFIG_PATH = Path("data/config/config.json")

class Config(BaseModel):
    program: ProgramConfig = Field(default_factory=ProgramConfig)
    proxies: ProxiesConfig = Field(default_factory=ProxiesConfig)
    session_pool: SessionPoolConfig = Field(default_factory=SessionPoolConfig)
    kemono_api: KemonoAPIConfig = Field(default_factory=KemonoAPIConfig)
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    
    def dict(self, *args, by_alias=True, **kwargs):
        return super().model_dump(*args, by_alias=by_alias, **kwargs)

class Settings(Config):
    def __init__(self):
        if not CONFIG_PATH.exists():
            self.init()
        else:
            self.load()
            self.save()
    
    def init(self):
        super().__init__()
        self.save()
        self.load()
    
    def load(self):
        data = json_load(CONFIG_PATH)
        obj = Config.model_validate(data)
        self.__dict__.update(obj.__dict__)
    
    def save(self, config_dict: dict = None):
        if config_dict is None:
            config_dict = self.dict()
        json_dump(config_dict, CONFIG_PATH)