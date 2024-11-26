from typing import Union
from kemonobakend.database.models import KemonoPostsInfoCreate, KemonoUser, KemonoUserCreate
from kemonobakend.kemono.builtins import posts_info_hash_id_func


def build_kemono_posts_info(user: Union[KemonoUser, KemonoUserCreate], posts_len: int):
    return KemonoPostsInfoCreate(
        hash_id = posts_info_hash_id_func(user.hash_id, user.updated),
        user_hash_id = user.hash_id,
        updated = user.updated,
        posts_length = posts_len,
        added_at = None,
        updated_at = None
    )

