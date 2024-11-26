import re
from yarl import URL
from typing import Optional, Union
from kemonobakend.utils import calc_str_sha256, calc_str_md5, json_dumps


SERVICES = (
    "patreon",
    "fanbox",
    "gumroad",
    "discord",
    "fantia",
    "dlsite",
    "afdian",
    "boosty",
    "subscribestar"
)

API_URL = "https://kemono.su/api/v1"
DATA_URL = "https://kemono.su/data"

PUBLIC_NAME_SERVICES_WITH_PRIORITY = (
    "fanbox",
    "patreon",
    "gumroad",
    "fantia",
    "discord",
    "subscribestar"
    "dlsite",
    "afdian",
    "boosty",
)

def select_public_user(all_users: list[dict]):
    '''select the public user from all_users list'''
    index_l = None
    for user in all_users:
        service = user.get("service")
        index = PUBLIC_NAME_SERVICES_WITH_PRIORITY.index(service)
        if index == 0:
            return user
        if index_l is None or index < index_l[0]:
            index_l = (index, user)
    return index_l[1]

def get_user_id_service_by_url(url: Union[str, URL]) -> tuple:
    if not isinstance(url, URL):
        url = URL(url)
    paths = url.path.split("/")
    user_id = None
    service = None
    for path in paths:
        if path == "user":
            user_id = paths[paths.index(path)+1]
        elif path in SERVICES:
            service = path
        elif path == "discord":
            # https://kemono.su/discord/server/814339508694155294#815230464306446346
            #                                       ^ server_id      ^ channel_id
            # server_id == user_id in this case
            service = "discord"
            server_id = paths[paths.index(path)+2]
            user_id = server_id if "#" not in server_id else server_id.split("#")[0]
            break
    return user_id, service

def base_hash_id_func(id, service):
    if service not in SERVICES:
        raise ValueError("Invalid service")
    index = hex(SERVICES.index(service))
    return f"{index}_{id}"

def creator_hash_id_func(id: str, public_name: str):
    return calc_str_md5(f"{id}_{public_name}")

def user_hash_id_func(id: str, service: str):
    return base_hash_id_func(id, service)

def post_hash_id_func(id: str, service: str):
    return base_hash_id_func(id, service)

def posts_info_hash_id_func(user_hash_id: str, updated: int):
    return calc_str_md5(f"{user_hash_id}_{updated}")

def attachment_hash_id_func(post_hash_id: str, sha256_like: str):
    return calc_str_sha256(f"{post_hash_id}_{sha256_like}")

def file_hash_id_func(save_path: str, sha256_like: str):
    return calc_str_sha256(f"{save_path}_{sha256_like}")

def formatter_params_hash_id_func(formatter_name: str, params: dict):
    # We just sorted the outermost keys of the params dict.
    # FIXME: Maybe we should sort the inner keys of the params dict as well.
    #        At least, the hash_id of the params is not necessary now.
    sorted_params = {k: params[k] for k in sorted(params.keys())}
    sorted_params_str = json_dumps(sorted_params)
    return calc_str_md5(f"{formatter_name}_{sorted_params_str}")

def get_sha256_from_path(path_like: Union[str, URL]) -> Optional[str]:
    if not isinstance(path_like, URL):
        path_like = URL(path_like)
    parts_reversed = path_like.parts[::-1]
    for part in parts_reversed:
        part = part.split(".")[0] if "." in part else part
        if part == "data":
            file_name = parts_reversed[0].split(".")[0] if "." in parts_reversed[0] else parts_reversed[0]
            if len(file_name) == 64 and file_name.isalnum():
                return file_name
            else:
                return None 
    else:
        for part in parts_reversed:
            part = part.split(".")[0] if "." in part else part
            if part.isalnum() and len(part) == 64:
                return part
    return None

strip_lst = ['表情、効果音差分', '表情差分', '効果音差分', '射精差分', 'ボテ差分', '【高画質版】', '+', '=', '×', '＋']

def strip_name(name: str):
    pattern = r'|'.join(map(re.escape, strip_lst))
    name_p = re.sub(pattern, '', name)
    return name_p
def format_name(name: str, max_num:int=64):
    name_p = strip_name(name)
    if len(name_p) > max_num:
        sp = name_p.split()
        if len(sp) > 1:
            s_n = ""
            s_n_lst = []
            for s in sp:
                s_n += s + " "
                s_n_lst.append(s_n)
            for s_n in s_n_lst:
                if len(s_n) <= max_num:
                    return s_n
        return name_p[:max_num]
    return name_p

def parse_user_id(user_id=None, service=None, server_id=None, url=None):
    if user_id and service:
        user_hash_id = user_hash_id_func(user_id, service)
    elif server_id:
        user_id = server_id
        service = 'discord'
        user_hash_id = user_hash_id_func(server_id, 'discord')
    elif url:
        user_id, service = get_user_id_service_by_url(url)
        user_hash_id = user_hash_id_func(user_id, service)
    elif user_id and "_" in user_id:
        user_hash_id = user_id
        user_id = user_id.split("_")[-1]
    return user_id, user_hash_id, service