import asyncio
import os
from pathlib import Path
from kemonobakend.database.models import KemonoUser
from kemonobakend.kemono.program import KemonoProgram, ProgramTools
from kemonobakend.kemono.files import KemonoFilesFormatter
from kemonobakend.kemono.resource_handler import ResourceHandler
from kemonobakend.session_pool import SessionPool
from kemonobakend.utils.progress import NormalProgress
from kemonobakend.log import logger

users = [
    "9016", "102545043", "11229342", "115051", 
    "13075529", "15966644", "16105069", "17332140", 
    "18095070", "273185", "28838", "29362997", "32465500", 
    "3316400", "49494721", "54024488", "544479", "5850450", 
    "59578913", "641955", "6570768", "66353827", "848240", 
    "8956113", "9343974", "97799", "99922406", "60070044", 
    "10706782", "49759620", "1067759931168", "1705682846638", 
    "683249661888", "8691714736262", "8717616750515", 
    "9106361094715", "8734481294487", "113743679596",
    "3757679648758", "11666662", "16112298", "49965584", 
    "54249020", "57750936", "26053475", "69653195","amato-bu"
]

services = [
    "fanbox", "fanbox", "fanbox", "fanbox", "fanbox", 
    "fanbox", "fanbox", "fanbox", "fanbox", "fanbox", 
    "fanbox", "fanbox", "fanbox", "fanbox", "fanbox", 
    "fanbox", "fanbox", "fanbox", "fanbox", "fanbox", 
    "fanbox", "fanbox", "fanbox", "fanbox", "fanbox", 
    "fanbox", "fanbox", "fanbox", "fanbox", "fanbox", 
    "gumroad", "gumroad", "gumroad", "gumroad", "gumroad", 
    "gumroad", "gumroad", "gumroad", "gumroad", "patreon", 
    "patreon", "patreon", "patreon", "patreon", "patreon", 
    "patreon", "subscribestar",
]

root = "G:/YOL/Kemono/Resource"
files_root = "G:/YOL/Kemono/KemonoManager"

def get_formatter(user: KemonoUser):
    formatter_name = user.public_name + "_" + user.hash_id
    return KemonoFilesFormatter(formatter_name, files_root)

async def get_has_posts_users(program: KemonoProgram):
    posts_infos = await program.get_posts_infos()
    user_hash_ids = [info.user_hash_id for info in posts_infos]
    async with program.session_context() as session:
        return await session.kemono_user.get_users(user_hash_ids)

async def get_users(urls, program):
    users = []
    for url in urls:
        users.append(await program.get_user(url = url))
    return users

async def update_users(urls, program: KemonoProgram):
    '''add users or update users'''
    async def update_user(url):
        try:
            await program.add_kemono_user(url = url)
            user = await program.get_user(url = url)
            await program.add_kemono_files(get_formatter(user), user)
            logger.info(f"Update user for {user.public_name}\t{user.service}")
        except Exception as e:
            logger.exception(e)
    
    await ProgramTools.async_with_progress(update_user, urls, f"Updating user")

async def hard_link_files(program: KemonoProgram, urls = None):
    async def hard_link_file(user: KemonoUser):
        try:
            f = get_formatter(user)
            files = await program.get_files_by_formatter_name(f.formatter_name)
            await program.hard_link_files(root, files, progress=progress)
            logger.info(f"Hard linked files for {user.public_name}\t({user.service})")
        except Exception as e:
            logger.exception(e)
    
    if urls is not None:
        users = await get_users(urls, program)
    else:
        users = await get_has_posts_users(program)
    with NormalProgress() as progress:
        await ProgramTools.async_with_progress(hard_link_file, users, f"Hard linking files", progress=progress)

async def update_formatter(user: KemonoUser, formatter: KemonoFilesFormatter, program: KemonoProgram):
    await program.add_kemono_files(formatter, user)
    files = await program.get_files_by_formatter_name(formatter.formatter_name)
    # if files:
    #     folder = Path(files[0].root) / "/".join(Path(files[0].folder).parts[:2])
    #     s = input(f"Remove {folder} ? [Y/N]: ")
    #     if s.lower() == "y" and folder.exists():
    #         os.remove(folder)
    await program.hard_link_files(root, files)

async def main():
    program = KemonoProgram()
    await program.init()
    urls = ["https://kemono.su/gumroad/user/9512949530480", "https://kemono.su/fanbox/user/569672", "https://kemono.su/fanbox/user/16731", "https://kemono.su/gumroad/user/683249661888"]
    await hard_link_files(program, urls)
    # user = await program.get_user(url = url)
    # await update_users(urls, program)
    
    # formatter_name = user.public_name + "_" + user.hash_id
    # formatter = KemonoFilesFormatter(formatter_name, files_root).with_default_folder_expr(
    #     [
    #         '"line" in post.title.lower() or "line" in attachment.name.lower() or (int(post.post_id) >= 107586413 and "png" in post.title.lower() and "uncensored" not in post.title.lower()),"line_art"',
    #     ]
    # )
    # await update_formatter(user, formatter, program)
    
    # urls = ["https://kemono.su/patreon/user/57750936", "https://kemono.su/patreon/user/16112298", "https://kemono.su/patreon/user/11666662", "https://kemono.su/patreon/user/69653195"]
    # await update_users(urls, program)
    # await hard_link_files(program)

    # async def add_files(user: KemonoUser):
    #     formatter_name = user.public_name + "_" + user.hash_id
    #     formatter = KemonoFilesFormatter(formatter_name, files_root)
    #     try:
    #         await program.add_kemono_files(formatter, user)
    #         logger.info(f"Added files for {user.public_name} ({user.service})")
    #     except Exception as e:
    #         logger.exception(e)
    
    # await ProgramTools.with_progress(add_files, users, "Generating files")
    
    # resource_handler = ResourceHandler(root)
    # await program.download_files_by_users(users, resource_handler)



policy = asyncio.WindowsSelectorEventLoopPolicy()
asyncio.set_event_loop_policy(policy)
asyncio.run(main())
