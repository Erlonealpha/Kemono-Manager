import re
from kemonobakend.database.models import KemonoPostCreate, KemonoPostsInfoCreate
from kemonobakend.kemono.builtins import user_hash_id_func, post_hash_id_func
from kemonobakend.utils import json_dumps


def build_kemono_post(info: KemonoPostsInfoCreate, **post_dic):
    from kemonobakend.database.model_builder import build_kemono_attachments, get_attachments_kwds_by_post
    
    def fill_nullables():
        if post_dic.get("server_id")  is None: post_dic["server_id"]  = "PLACEHOLDER"
        if post_dic.get("channel_id") is None: post_dic["channel_id"] = "PLACEHOLDER"
        if post_dic.get("user_id")    is None: post_dic["user_id"]    = "PLACEHOLDER"
    def dump(obj, default=None):
        if not isinstance(obj, str):
            try:
                obj = json_dumps(obj) if obj else default
            except:
                obj = default
        return obj
    post_dic["post_id"]   = post_dic.pop("id", None)
    r = re.compile(r'(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?«»“”‘’]))')
    links = r.findall(post_dic.get("content", ""))
    post_dic["links"]     = dump(links, "[]")
    service = post_dic.get("service")
    if service is None or service == "discord":
        post_dic["service"]       = "discord"
        post_dic["server_id"]     = post_dic.pop("server", None)
        post_dic["channel_id"]    = post_dic.pop("channel", None)
        post_dic["author"]        = dump(post_dic.get("author"), "{}")
        post_dic["embeds"]        = dump(post_dic.get("embeds"), "[]")
        post_dic["mentions"]      = dump(post_dic.get("mentions"), "[]")
    else:
        post_dic["user_id"]       = post_dic.pop("user", None)
        embed                     = post_dic.pop("embed", None)
        post_dic["embeds"]        = f"[{dump(embed, "{}")}]" if embed else "[]"
        post_dic["poll"]          = dump(post_dic.get("poll"), None)
        post_dic["captions"]      = dump(post_dic.get("captions"), None)
        post_dic["tags"]          = dump(post_dic.get("tags"), None)
    post_dic["hash_id"]       = post_hash_id_func(post_dic["post_id"], post_dic["service"])
    post_dic["user_hash_id"]  = user_hash_id_func(post_dic.get("user_id") or post_dic.get("server_id"), post_dic["service"])
    
    fill_nullables()
    attachments = get_attachments_kwds_by_post(post_dic)
    post_dic.pop("attachments", None)
    post_dic.pop("resources", None)
    post_dic.pop("file", None)
    post = KemonoPostCreate(posts_info_hash_id=info.hash_id, **post_dic)
    post.info = info
    post.attachments = build_kemono_attachments(info.user_hash_id, post.hash_id, attachments)
    return post

