from kemonobakend.downloader import Downloader, DownloadProperties
from kemonobakend.database import AsyncCombineSession
from kemonobakend.database.models import KemonoAttachment
from kemonobakend.session_pool import SessionPool
from kemonobakend.api import KemonoAPI
from kemonobakend.log import logger

from .builtins import parse_user_id, user_hash_id_func, get_user_id_service_by_url
from .resource_handler import ResourceHandler


async def download_by_user(
    root, 
    tmp_path=None, 
    user_id=None, service=None, server_id=None, url=None,
    engine=None, 
    downloader: Downloader = None,
    session_pool=None, 
    filter=None,
    wait: bool = True,
):
    def remove_duplicates(files: list[KemonoAttachment]):
        seen = set()
        return [file for file in files if file.sha256 is None or (file.sha256 not in seen and not seen.add(file.sha256))]
    res_handler = ResourceHandler(root)
    
    user_id, user_hash_id, service = parse_user_id(user_id, service, server_id, url)
    async with AsyncCombineSession(engine) as session:
        files = await session.kemono_attachment.get_attachments_by_user(user_hash_id)
    
    files = remove_duplicates(files)
    files = [file for file in files if not res_handler.exists(file.sha256, file.hash_id)]
    
    if downloader is None:
        session_pool = session_pool or SessionPool(enabled_accounts_pool=True)
        prop = DownloadProperties(
            session_pool=session_pool,
            tmp_path = tmp_path,
            max_tasks_concurrent = 6,
            per_task_max_concurrent = 16,
        )
        await prop.session_pool.wait_init_check_proxies()
        downloader = Downloader(prop)

    if not downloader.is_running:
        downloader.start()
    downloader.prop.progress_tracker.add_main_task(f"Downloading {len(files)} files for user {user_hash_id}", len(files))

    for file in files:
        save_path = res_handler.get_path(file.sha256, file.hash_id)
        await downloader.create_task(file.path, save_path, file.sha256, file.size)
    
    if wait:
        await downloader.wait_forever()

