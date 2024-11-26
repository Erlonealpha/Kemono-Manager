from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine

from kemonobakend.config import settings

engine = create_async_engine("sqlite+aiosqlite:///" + settings.program.database_path)

_db_path = Path(settings.program.database_path)
if not _db_path.parent.exists():
    _db_path.parent.mkdir(parents=True)
