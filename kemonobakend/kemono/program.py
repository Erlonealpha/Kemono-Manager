import asyncio
from contextlib import asynccontextmanager
from bidict import bidict
from shutil import move as shutil_move
from asyncstdlib.builtins import map as amap, list as alist
from typing import Optional, Union

from kemonobakend.database import AsyncCombineSession, create_all
from kemonobakend.database.model_builder import build_kemono_posts_info
from kemonobakend.database.models import KemonoUser, KemonoUserCreate, KemonoFile, KemonoAttachment, KemonoPostsInfo
from kemonobakend.session_pool import SessionPool
from kemonobakend.downloader import Downloader, DownloadProperties
from kemonobakend.api import KemonoAPI
from kemonobakend.database.engine import engine as e
from kemonobakend.utils import path_exists, MKLink
from kemonobakend.utils.progress import NormalProgress, DownloadProgress
from kemonobakend.log import logger

from .builtins import parse_user_id
from .files import KemonoFilesFormatter
from .resource_handler import ResourceHandler

class KemonoProgram:
    def __init__(self, session_pool=None, database_engine=e):
        self.session_pool = session_pool or SessionPool(enabled_accounts_pool=True)
        self.kemono_api = KemonoAPI(session_pool=self.session_pool)
        self.database_engine = database_engine
    
    async def init(self):
        await create_all(self.database_engine)
        await self.session_pool.wait_init_check_proxies()
    
    @asynccontextmanager
    async def session_context(self):
        async with AsyncCombineSession(self.database_engine) as session:
            yield session
    
    async def get_user(self, user_id=None, service=None, server_id=None, url=None, all_users=True):
        if isinstance(user_id, KemonoUser):
            return user_id
        user_id, user_hash_id, service = parse_user_id(user_id, service, server_id, url)
        async with self.session_context() as session:
            return await session.kemono_user.get_user(user_hash_id, all_users=all_users)

    async def get_all_users(self) -> list[KemonoUser]:
        async with self.session_context() as session:
            return await session.kemono_user.get_all()
    
    async def get_posts_infos(self) -> list[KemonoPostsInfo]:
        async with self.session_context() as session:
            return await session.kemono_posts_info.get_all()
    
    async def get_files_by_formatter_name(self, formatter_name: str):
        async with self.session_context() as session:
            return await session.kemono_file.get_files_by_formatter_name(formatter_name)
    
    async def add_kemono_user(self, user_id=None, service=None, server_id=None, url=None):
        def get_current_user(users: list[Union[KemonoUser, KemonoUserCreate]], is_index: bool = False) -> Optional[Union[KemonoUser, KemonoUserCreate, int]]:
            for i, user in enumerate(users):
                if user.user_id == user_id:
                    if is_index:
                        return i
                    return user
            return None
        
        user_id, user_hash_id, service = parse_user_id(user_id, service, server_id, url)

        creator_now = await self.kemono_api.kemono_creators.create_creator(user_hash_id)
        if creator_now is None:
            creator_now = await self.kemono_api.kemono_creators.get_creator(user_hash_id)
        kemono_user_now = get_current_user(creator_now.kemono_users)
        if kemono_user_now is None:
            raise Exception("Uncertain Error: Kemono user not found in creator")
        
        async with self.session_context() as session:
            kemono_user_exist: KemonoUser = await session.kemono_user.get_user(user_hash_id, all_users=True)
            all_users_exist = None
            creator_exist = None
            if kemono_user_exist:
                creator_exist = kemono_user_exist.kemono_creator
                # await session.run_sync(lambda _ : creator_exist.kemono_users)
            else:
                # first try get users by link accounts
                all_users_exist = await session.kemono_user.get_users([u.hash_id for u in creator_now.kemono_users])
                if all_users_exist:
                    creator_exist = all_users_exist[0].kemono_creator
            
            commit = False
            kemono_user = None
            if creator_exist is None:
                # add new creator
                await session.kemono_creator.add_creator(creator_now, commit=False)
                for i in range(len(creator_now.kemono_users)):
                    creator_now.kemono_users[i] = await session.kemono_user.add_user(creator_now.kemono_users[i], commit=False)
                kemono_user = get_current_user(creator_now.kemono_users)
                commit = True
            else:
                # first check current user's updated time
                if kemono_user_exist is not None and kemono_user_exist.updated < kemono_user_now.updated:
                    kemono_user_exist.sqlmodel_update(kemono_user_now)
                    session.kemono_user.update(kemono_user_exist, commit=False)
                    commit = True
                
                # check creator public data
                if creator_now.hash_id != creator_exist.hash_id:
                    # update creator public data
                    for user in creator_now.kemono_users:
                        user_exist = await session.kemono_user.get_user(user.hash_id)
                        if user_exist:
                            user_exist.sqlmodel_update(user)
                            session.kemono_user.update(user_exist, commit=False)
                        else:
                            session.kemono_user.add_user(user, commit=False)
                    kemono_user = get_current_user(creator_now.kemono_users)
                    commit = True
                else:
                    kemono_user = get_current_user(creator_exist.kemono_users)

            try:
                # commit users and creator to database
                if commit:
                    await session.commit()
            except Exception as e:
                logger.error(f"Error getting kemono users and creator: {e}")
                await session.rollback()
            
            posts_info_exist = await session.kemono_posts_info.get_info_by_user_hash_id(user_hash_id)
            if (posts_info_exist and posts_info_exist.updated < kemono_user_now.updated) or posts_info_exist is None:
                posts = await self.kemono_api.kemono_posts.build_all_posts(kemono_user_now)
                info = posts[0].info
                if posts_info_exist is not None:
                    posts_info_exist.sqlmodel_update(info)
                    await session.kemono_posts_info.update(posts_info_exist, commit=False)
                    await session.kemono_post.delete_all_by_info(info.hash_id, commit=False)
                    await session.kemono_attachment.delete_all_by_user(user_hash_id, commit=False)
                else:
                    await session.kemono_posts_info.add_info(info, commit=False)
                await session.kemono_post.add_posts(posts, commit=False)
                for post in posts:
                    await session.kemono_attachment.add_attachments(post.attachments, commit=False)
                try:
                    # commit posts and attachments to database
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Error adding kemono user: {e}")
                    return None
        return kemono_user
    
    async def update_kemono_user(self, user_id=None, service=None, server_id=None, url=None):
        pass
    
    async def add_kemono_posts(self):
        pass

    async def update_kemono_posts(self):
        pass

    async def add_kemono_files(self, formatter: KemonoFilesFormatter, user_id=None, service=None, server_id=None, url=None, update=True):
        kemono_user = await self.get_user(user_id, service, server_id, url)
        async with self.session_context() as session:
            posts = await session.kemono_post.get_posts_by_user(kemono_user.hash_id)
            if not posts:
                logger.warning(f"No posts found for user {kemono_user.user_id}")
                return
            files_exist = await session.kemono_file.get_files_by_formatter_name(formatter.formatter_name)
            formatter_params = await session.formatter_param.get_param(formatter.formatter_name)
        need_delete = False
        # We not use db data in session, may ROLLBACK in case of relation loaded
        if files_exist:
            if not update:
                logger.warning(f"Kemono files already exist for user {kemono_user.user_id} with formatter {formatter.formatter_name}")
                return
            need_delete = True
        files = await formatter.generate_files(kemono_user, posts)
        
        async with self.session_context() as session:
            if formatter_params is None:
                await session.formatter_param.add_param_by_kwd(formatter.formatter_name, commit=False, **formatter.get_params())
            else:
                formatter_params.sqlmodel_update(formatter.get_params())
                await session.formatter_param.update(formatter_params, commit=False)
            if need_delete:
                await session.kemono_file.delete_files_by_formatter_name(formatter.formatter_name, commit=False)
            await session.kemono_file.add_files(files, commit=False)
            
            try:
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Error adding kemono files: {e}")

    async def update_kemono_files(self, formatter):
        pass
    
    async def hard_link_files(self, res_root: str, kemono_files: list[KemonoFile], warn = False, progress: Optional[DownloadProgress] = None):
        hard_link_map = {}
        res_handler = ResourceHandler(res_root)
        
        def get_need_link_files(kemono_file: KemonoFile):
            res_path = res_handler.get_path(kemono_file.sha256, kemono_file.attachment_hash_id)
            if not res_path.exists():
                if warn:
                    logger.warning(f"File {res_path} not exists, skip hard link")
            elif path_exists(kemono_file.save_path):
                if warn:
                    logger.warning(f"File {kemono_file.save_path} already exists, skip hard link")
            else:
                hard_link_map[kemono_file.save_path] = res_path

        ProgramTools.with_progress(get_need_link_files, kemono_files, "Getting need link files", progress=progress)
        
        async def hard_link_file(t):
            target, rel = t
            try:
                MKLink.create_hard_link(target, rel)
            except Exception as e:
                logger.error(f"Failed to hard link {rel} -> {target}, {e}")

        await ProgramTools.async_with_progress(hard_link_file, hard_link_map.items(), "Hard Linking", progress=progress)
    
    @staticmethod
    async def check_resource(resource_handler: ResourceHandler, files: list[KemonoFile]):
        sha256_map = bidict() # K: original sha256(file_name), V: actual sha256
        with NormalProgress() as progress:
            task = progress.add_task("Checking resource", total=len(files))
            for file in files:
                if file.sha256 is not None and resource_handler.exists(file.sha256):
                    sha256_calc = await resource_handler.async_get_file_hash(file.sha256)
                    if sha256_calc != file.sha256:
                        if resource_handler.exists(sha256_calc):
                            sha256_map[file.sha256] = sha256_calc
                            resource_handler.move_to_tmp(file.sha256)
                            logger.warning(f"Current file {file.file_name}'s sha256 is another file's sha256")
                        else:
                            logger.warning(f"Current file {file.file_name} has different sha256: {file.sha256} -> {sha256_calc}, remove it")
                            resource_handler.remove(file.sha256)
                task.advance()
            
            for sha256, actual_sha256 in sha256_map.items():
                if actual_sha256 in sha256_map:
                    logger.info(f"File {sha256} has been linked to {actual_sha256}")
                    shutil_move(resource_handler.get_tmp_path(sha256), resource_handler.get_path(actual_sha256))
                else:
                    logger.info(f"File {sha256} -> {actual_sha256}")
    
    async def download_files_by_users(self, users: list[KemonoUser], resource_handler: ResourceHandler, downloader: Downloader = None, filter = None):
        def remove_duplicates(files: list[KemonoAttachment]):
            seen = set()
            return [file for file in files if file.sha256 is None or (file.sha256 not in seen and not seen.add(file.sha256))]
        def remove_existed(files: list[KemonoAttachment]):
            return [file for file in files if not resource_handler.exists(file.sha256, file.hash_id)]
        async def get_all_attachments(user: KemonoUser):
            posts = await session.kemono_post.get_posts_by_user(user.hash_id)
            attachments = []
            for post in posts:
                attachments.extend(post.attachments)
            attachments = remove_duplicates(attachments)
            attachments = remove_existed(attachments)
            if filter is not None:
                # TODO: filter attachments
                ...
            all_attachments.extend(attachments)
            logger.info(f"User {user.name} has {len(attachments)} attachments")
            
        if downloader is None:
            prop = DownloadProperties(
                self.session_pool,
                max_tasks_concurrent = 12,
                per_task_max_concurrent = 12,
            )
            downloader = Downloader(prop)
        
        if not downloader.is_running:
            downloader.start()
        
        async with self.session_context() as session:
            all_attachments: list[KemonoAttachment] = []
            await ProgramTools.async_with_progress(get_all_attachments, users, "Getting attachments")
        downloader.prop.progress_tracker.add_main_task(f"Downloading {len(all_attachments)} files", len(all_attachments))
        for attachment in all_attachments:
            save_path = resource_handler.get_path(attachment.sha256, attachment.hash_id)
            await downloader.create_task(attachment.path, save_path, attachment.sha256, attachment.size, attachment.sha256)
    
        # await downloader.wait_any_tasks_done(len(all_attachments))
        await downloader.wait_forever()

class ProgramTools:
    @staticmethod
    async def async_with_progress(func, iterable, desc, remove_after=True, progress: Optional[DownloadProgress] = None):
        async def async_wrap(item):
            try:
                return await func(item)
            finally:
                task.advance()
        
        if progress is None:
            progress_ = NormalProgress().__enter__()
        else:
            progress_ = progress
        task = progress_.add_task(desc, "Awaiting", total=len(iterable))
        try:
            return await alist(amap(async_wrap, iterable))
        finally:
            if remove_after:
                task.remove()
            if progress is None:
                progress_.__exit__(None, None, None)
    
    def with_progress(func, iterable, desc, remove_after=True, progress: Optional[DownloadProgress] = None):
        def wrap(item):
            try:
                return func(item)
            finally:
                task.advance()
                
        if progress is None:
            progress_ = NormalProgress().__enter__()
        else:
            progress_ = progress
        task = progress_.add_task(desc, "Awaiting", total=len(iterable))
        try:
            return list(map(wrap, iterable))
        finally:
            if remove_after:
                task.remove()
            if progress is None:
                progress_.__exit__(None, None, None)
