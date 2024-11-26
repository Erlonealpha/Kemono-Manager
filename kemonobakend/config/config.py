from pydantic import BaseModel, Field
from typing import TypeVar, Union, Any

Proxy = TypeVar("Proxy")

class ProgramConfig(BaseModel):
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="logs/kemonobakend.log")
    database_path: str = Field(default="data/db/kemonobakend.db")

class ProxiesConfig(BaseModel):
    default_proxies: Union[str, list[Proxy]] = Field(default="fanqie_01")
    proxy_test_timeout: dict = Field(default={"total": 18, "connect": 12})

class SessionPoolConfig(BaseModel):
    elp_threshold: float = Field(default=0.4)

class KemonoAPIConfig(BaseModel):
    get_discord_channel_all_posts_timeout: int = Field(default=60)
    
class DownloadConfig(BaseModel):
    max_concurrent_downloads: int = Field(default=8)
    max_concurrent_task: int = Field(default=16)
    max_retries: int = Field(default=3)
    timeout_kwargs: dict = Field(default={"connect": 10})
    tmp_path: str = Field(default="downloads/tmp")
    auto_chunks_dict: dict = Field(default={
        "0-2MB": 4,
        "2-5MB": 6,
        "5-10MB": 8,
        "10-20MB": 10,
        "20-50MB": 16,
        "50-200MB": 24,
        "200-1024MB": 64,
        "1024MB-": 128
    })
