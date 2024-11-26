if __name__ == '__main__':
    import sys, os
    sys.path.append(os.getcwd())

import asyncio
from rich import print
from kemonobakend.database import AsyncCombineSession
from sqlalchemy.ext.asyncio import create_async_engine

from kemonobakend.session_pool import SessionPool
from kemonobakend.api.kemono import KemonoAPI
from kemonobakend.utils import path_join, calc_file_sha256
from kemonobakend.log import logger


user_dic_example = {
    "id": "10446621",
    "name": "darmengine",
    "service": "fanbox",
    "indexed": 1640627543,
    "updated": 1718747942,
    "favorited": 1653
}

user_dic_example2 = {
    "id": "48028427",
    "name": "YuriEBD",
    "service": "patreon",
    "indexed": 1697240251,
    "updated": 1724674785,
    "favorited": 128
}

post_dic_example = {
    "id": "8007816",
    "user": "49494721",
    "service": "fanbox",
    "title": "ニコ・デマラ　表情、効果音差分",
    "content": "",
    "embed": {},
    "shared_file": False,
    "added": "2024-05-31T11:46:47.949204",
    "published": "2024-05-31T07:44:00",
    "edited": "2024-05-31T07:44:00",
    "file": {
        "name": "I8uwp8A8cKpeiWF9RlISgun6.jpeg",
        "path": "/60/29/60291e2ecb5a8e5952de0fdfb8e140786725dd3060639df7e69cf701e4e4926c.jpg"
    },
    "attachments": [
        {
        "name": "I8uwp8A8cKpeiWF9RlISgun6.jpeg",
        "path": "/60/29/60291e2ecb5a8e5952de0fdfb8e140786725dd3060639df7e69cf701e4e4926c.jpg",
        "type": "cover"
        },
        {
            "name": "91SdIh0Ksue0rGXIe16Q7Nv2.png",
            "path": "/7e/ff/7eff59c3fb563dc49db8a3194eb0e4b03079d63b754f0970da01fef5084f87ec.png"
        },
        {
            "name": "plMCAcbh5FS9Xj32HXnxlTWl.png",
            "path": "/c2/73/c273c01f62e118172ee571ff1898987c2b763f6b44426f1f23cf7e327aa3e936.png"
        },
        {
            "name": "AlY4nRtXTXJ382xyMIoFz3av.png",
            "path": "/38/b9/38b941cf26998f43977af82536cba24f9d20b185c52c057dae13e389bff571d5.png"
        },
        {
            "name": "j9PJOAxYHXAWIjjLAs4EImVe.png",
            "path": "/c2/44/c244acda56ea6888efcd2724b0087bcf2d1d52eaf1f9f669fc62a50d7f78c342.png"
        },
        {
            "name": "SR0pyjpLt7hDKh4e7EbGNmSc.png",
            "path": "/fd/84/fd844dff2b4cc420a6a569ad7cc3889c557ee4cd3fe19ea60b30de9afb8046d6.png"
        },
        {
            "name": "X3U5ocME0YwWZFVbICdMLNps.png",
            "path": "/65/0d/650ddb6e9856529dcecc9fcc2b388b23c05263acbd5a1638c6ffedb5c584f30e.png"
        },
        {
            "name": "W53eGlVu94PqSFNz8xBVCwme.png",
            "path": "/cb/fd/cbfdd0b09fb9bd769dc899db7e23e03e61b2b9ab79fa67b0085e5f3d232629f9.png"
        },
        {
            "name": "bLnzSxeI4gXhwHFO5HVv3oFf.png",
            "path": "/76/5d/765d72d113d0cb1b5e932fb72dc2a099cde8f35fa3850d0435dfa28eec2a54ad.png"
        },
        {
            "name": "eceTkDa8to3kjHI2X9WGHCkl.png",
            "path": "/65/af/65af2d6b3fc32992fb2033555cd30843e71cb708022eaa8c709630e69e717769.png"
        },
        {
            "name": "Yw7kDHtWKx1vwfodLTlSwjLL.png",
            "path": "/fb/17/fb1798330679efe642dd6a8faf1ed414e9296b2e5dad9c7b72bbf465efd409da.png"
        }
    ],
    "poll": None,
    "captions": None,
    "tags": None
}

def hard_link_to_resource(res_root, target_path):
    from kemonobakend.utils.progress import NormalProgress
    from kemonobakend.utils.mklink import MKLink
    length = len([
        f 
        for _, _, files in os.walk(target_path)
        for f in files
    ])
    with  NormalProgress() as progress:
        task = progress.add_task("Hard Linking", total=length)
        for root, dirs, files in os.walk(target_path):
            for file in files:
                path = path_join(root, file)
                sha256 = calc_file_sha256(path)
                target = path_join(res_root, sha256[:2], sha256[2:4], sha256)
                try:
                    if os.path.exists(target):
                        continue
                    MKLink.create_hard_link(target, path)
                except:
                    logger.error(f"Failed to create hard link {path} -> {target}")
                finally:
                    task.advance(1)

def two2three_floor(path=r"G:\YOL\Kemono\Resource"):
    from kemonobakend.utils.progress import NormalProgress
    from pathlib import Path
    from shutil import move
    path = path
    length = len([
        f 
        for _, _, files in os.walk(path)
        for f in files
    ])
    with  NormalProgress() as progress:
        task = progress.add_task("Moving", total=length)
        for root, _, files in os.walk(path):
            for file in files:
                raw_path = path_join(root, file)
                new_path = path_join(root, file[2:4], file)
                try:
                    new_path_ = Path(new_path)
                    if not new_path_.parent.exists():
                        new_path_.parent.mkdir(parents=True)
                    move(raw_path, new_path)
                except:
                    logger.error(f"Failed to move {raw_path} -> {new_path}")
                finally:
                    task.advance(1)

async def test_database():
    engine = create_async_engine("sqlite+aiosqlite:///test/test.db", echo=True)
    async with AsyncCombineSession(engine) as session:
        await session.drop_all()
        await session.create_all()
        # await session.migrate()
        
        user = await session.kemono_user.add_user_by_kwd(**user_dic_example2)
        users = await session.kemono_user.get_all()
        print([user.model_dump() for user in users])
        
        await session.kemono_post.add_post_by_kwd(**post_dic_example)
        posts = await session.kemono_post.get_all()
        print([post.model_dump() for post in posts])
        
        post = posts[0]
        attachments = post_dic_example.get("attachments")
        await session.kemono_attachment.add_attachments_by_kwds(attachments, post.hash_id)
        files = await session.kemono_attachment.get_all()
        print([file.model_dump() for file in files])
        print("done")

async def test_session_pool():
    session_pool = SessionPool()
    sessions = [
        session_pool.get_nowait()
        for _ in range(50)
    ]
    print([(s.proxy, s.proxy.priority) for s in sessions])
    for session in sessions:
        await session_pool.put(session)
    
    async with session_pool.get() as session:
        print(session.proxy)

async def test_kemono_api():
    api = KemonoAPI()
    await api.session_pool.wait_init_check_proxies()
    
    creators = await api.list_creators()
    # posts = await api.get_creator_all_posts("fanbox", "3316400")
    # print(len(posts), "\n", posts[:10])
    posts_discord = await api.get_discord_channel_all_posts("892554014074482729")
    print(len(posts_discord), "\n", posts_discord[:10])

async def test_kemono_api_async(api: KemonoAPI):
    fd = await api.get_archive_details("8128b0d565154b33930d8ae7f89d22b909872fba129d9b239c3388e5dcc17aaf")

async def test_downloader():
    from kemonobakend.downloader import Downloader, ProgressTracker
    # progress_tracker = ProgressTracker()
    session_pool = SessionPool()
    await session_pool.wait_init_check_proxies()
    # await session_pool.check_proxies(semaphore=4)
    downloader = Downloader()
    downloader_looper_task = downloader.start()
    # url = "https://kemono.su/10/cd/10cdb65213ffa7c61d0541a5455ea8ebb515fba3239d59168ac086f15464de7b.mp4"
    # url = "https://n4.kemono.su/data/7e/10/7e103e09c1b793c0af6369fcf550b1546758ed8803ec9d2ca095e34c618cfe7d.mp4"
    url = "https://n3.kemono.su/data/d4/d1/d4d174e8279b5c5fcf9b9a2f8614b759284d69c4112cc77df073e55a21cdc864.psd"
    # save_path = "test/St.Louis Reward.mp4"
    # file_name = "St.Louis Reward.mp4"
    # save_path = "test/Bonus - Xray Version(only the last Scene).mp4"
    save_path = "test/Scene1v2.psd" 
    # file_name = "Bonus - Xray Version(only the last Scene).mp4"
    file_name = "Scene1v2.psd" 
    task_id = await downloader.create_task(url, save_path, file_name)
    # await downloader.wait_for_task(task_id)
    
    # await downloader.stop()
    await asyncio.wait_for(downloader_looper_task, timeout=None)

async def test_add_kemono_user(*url):
    from kemonobakend.kemono.program import KemonoProgram
    from kemonobakend.database import create_all, drop_all
    engine = create_async_engine("sqlite+aiosqlite:///test/test_user.db")
    # await drop_all(engine)
    await create_all(engine)
    if not isinstance(url, (list, tuple)):
        url = [url]
    session_pool = SessionPool(enabled_accounts_pool=True)
    await session_pool.wait_init_check_proxies()
    kemono_program = KemonoProgram(session_pool, engine)
    for url_ in url:
        await kemono_program.add_kemono_user(url=url_)

async def test_download_user(*url):
    from kemonobakend.database import AsyncCombineSession, create_all 
    from kemonobakend.kemono.user import download_by_user
    from kemonobakend.downloader import Downloader, DownloadProperties
    engine = create_async_engine("sqlite+aiosqlite:///test/test_user.db", echo=True)
    await create_all(engine)
    
    prop = DownloadProperties(
        max_tasks_concurrent=16,
        per_task_max_concurrent=10,
        tmp_path="G:/YOL/Kemono/ResourceTemp/tmp"
    )
    await prop.session_pool.wait_init_check_proxies()
    downloader = Downloader(prop)
    downloader.start()
    for url_ in url:
        await download_by_user(root="G:/YOL/Kemono/Resource", url=url_, engine=engine, downloader=downloader, wait=False)
    await downloader.wait_forever()

async def test_files_formatter(url, pub=False):
    from kemonobakend.database import AsyncCombineSession, create_all 
    from kemonobakend.kemono.user import parse_user_id
    from kemonobakend.kemono.files import KemonoFilesFormatter
    from kemonobakend.kemono.program import KemonoProgram
    engine = create_async_engine("sqlite+aiosqlite:///test/test_user.db")
    await create_all(engine)
    session_pool = SessionPool(enabled_accounts_pool=True)
    await session_pool.wait_init_check_proxies()
    kemono_program = KemonoProgram(session_pool, engine)
    _, user_hash_id, _ = parse_user_id(url = url)
    folder_expr = \
'''
base_dir = path_join(creator.service, creator.name)
if attachment.type == "cover":
    folder = "cover"
elif attachment.type == "thumbnail":
    folder = "thumbnail"
else:
    folder = get_folder_by_filetype(file_type)
return path_join(base_dir, folder)
''' if not pub else \
'''
base_dir = path_join(creator.public_name, creator.service)
if attachment.type == "cover":
    folder = "cover"
elif attachment.type == "thumbnail":
    folder = "thumbnail"
else:
    folder = get_folder_by_filetype(file_type)
return path_join(base_dir, folder)
'''
    file_expr = \
'''
f, ext = path_splitext(attachment.name)
return by_alpha_condition(f, post.title) + ext
''' 
    if pub:
        user = await kemono_program.get_user(user_hash_id)
        formatter_name = user.public_name + "_" + user_hash_id
    else:
        formatter_name = user_hash_id
    formatter = KemonoFilesFormatter(
        formatter_name,
        "G:/YOL/Kemono/KemonoManager",
        folder_expr=folder_expr,
        file_expr=file_expr,
    )
    await kemono_program.add_kemono_files(formatter, user_hash_id)

async def test_files_hard_link(url, pub=False):
    from kemonobakend.database import AsyncCombineSession, create_all 
    from kemonobakend.kemono.user import parse_user_id
    from kemonobakend.kemono.files import KemonoFilesFormatter, hard_link_files
    engine = create_async_engine("sqlite+aiosqlite:///test/test_user.db", echo=True)
    await create_all(engine)
    async with AsyncCombineSession(engine) as session:
        user_id, user_hash_id, service = parse_user_id(url = url)
        if pub:
            user = await session.kemono_user.get_user(user_hash_id)
            formatter_name = user.public_name + "_" + user_hash_id
        else:
            formatter_name = user_hash_id
        files = await session.kemono_file.get_files_by_formatter_name(formatter_name)
        await hard_link_files("G:/YOL/Kemono/Resource", files)

async def test_account_pool():
    from kemonobakend.accounts_pool.accounts_register import AccountRegister
    session_pool = SessionPool()
    await session_pool.wait_init_check_proxies()
    register = AccountRegister(session_pool)
    await register.login_accounts_auto("prowizdther", 100)

async def test_check_files(url, pub=False):
    from kemonobakend.database import AsyncCombineSession, create_all 
    from kemonobakend.kemono.user import parse_user_id
    from kemonobakend.kemono.program import KemonoProgram
    from kemonobakend.kemono.resource_handler import ResourceHandler
    engine = create_async_engine("sqlite+aiosqlite:///test/test_user.db", echo=True)
    await create_all(engine)
    async with AsyncCombineSession(engine) as session:
        user_id, user_hash_id, service = parse_user_id(url = url)
        if pub:
            user = await session.kemono_user.get_user(user_hash_id)
            formatter_name = user.public_name + "_" + user_hash_id
        else:
            formatter_name = user_hash_id
        files = await session.kemono_file.get_files_by_formatter_name(formatter_name)
        resource_handler = ResourceHandler("G:/YOL/Kemono/Resource")
        await KemonoProgram.check_resource(resource_handler, files)

async def main_test():
    # await test_download_user("https://kemono.su/patreon/user/16112298")
    # await test_check_files("https://kemono.su/patreon/user/16112298", pub=True)
    # await test_files_formatter("https://kemono.su/patreon/user/16112298", pub=True)
    await test_files_hard_link("https://kemono.su/patreon/user/16112298", pub=True)
    pass

if __name__ == '__main__':
    # two2three_floor()
    # hard_link_to_resource(r"G:\YOL\Kemono\Resource", r"G:\YOL\Kemono\KemonoManager\gumroad\topu")
    try:
        # asyncio.run(test_add_kemono_user("https://kemono.su/patreon/user/16112298"))
        # asyncio.run(test_files_formatter("https://kemono.su/patreon/user/16112298"))
        asyncio.run(main_test())
        # asyncio.run(test_account_pool())
        # asyncio.run(test_download_user("https://kemono.su/patreon/user/16112298"))
        pass
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt")
