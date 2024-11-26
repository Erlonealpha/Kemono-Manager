from kemonobakend.database.models import KemonoAttachmentCreate
from kemonobakend.kemono.builtins import attachment_hash_id_func, get_sha256_from_path, DATA_URL


def get_attachments_kwds_by_post(post) -> list[dict]:
    def path(p, i=None):
        if isinstance(p, str):
            return DATA_URL + p
        else:
            if path := p.get("path"):
                if not path.startswith("http"):
                    p["path"] = DATA_URL + path
                if i is not None:
                    p["idx"] = i
                return p
    service = post.get("service")
    is_patreon = service == "patreon"
    is_discord = service == "discord"
    if is_discord:
        return post.get("attachments")
    attachments = [path(p, i) for i, p in enumerate(post.get("attachments"))]
    file = post.get("file")
    cover = None
    thumbnail = None
    if file and not is_patreon:
        cover = path(file)
        
        if _thumbnail := file.get('thumbnail'):
            thumbnail = path(_thumbnail)
        
        if covers := file.get('covers'):
            idx = attachments[-1].get("idx") + 1 if attachments else 0
            for _cover in covers:
                if _cover.get("main_cover"):
                    cover = {"name": _cover['original']['name'], "path": path(_cover['original']['path'])}
                else:
                    attachments.append(path(_cover["original"], idx))
                    idx += 1
    if cover:
        cover["idx"] = -1
        cover["type"] = "cover"
        attachments.append(cover)
    if thumbnail:
        thumbnail["idx"] = -2
        thumbnail["type"] = "thumbnail"
        attachments.append(thumbnail)
    return attachments

def build_kemono_attachment_by_kwd(user_hash_id, post_hash_id, **kwd):
    if not (sha256 := kwd.get("sha256")):
        sha256 = get_sha256_from_path(kwd.get("path"))
        kwd["sha256"] = sha256
    if not (_post_hash_id := kwd.get("post_hash_id")):
        kwd["post_hash_id"] = post_hash_id
        _post_hash_id = post_hash_id
    kwd["hash_id"] = attachment_hash_id_func(_post_hash_id, sha256 or kwd.get("path"))
    kwd["hash_id_type"] = "sha256" if sha256 else "url"
    kwd["user_hash_id"] = user_hash_id
    return KemonoAttachmentCreate(**kwd)

def build_kemono_attachments(user_hash_id, post_hash_id, args):
    '''name path type size sha256 post_hash_id'''
    return [
        build_kemono_attachment_by_kwd(user_hash_id, post_hash_id, **kwd)
        for kwd in args
    ]

