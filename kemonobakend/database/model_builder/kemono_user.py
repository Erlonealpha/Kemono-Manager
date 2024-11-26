from kemonobakend.database.models import KemonoCreatorCreate, KemonoUserCreate
from kemonobakend.kemono.builtins import user_hash_id_func, select_public_user
from kemonobakend.utils import json_dumps

def build_kemono_user_by_creator(creator: KemonoCreatorCreate, **kwargs):
    user = build_kemono_user_by_kwd(no_creator=True, **kwargs)
    user.kemono_creator = creator
    return user

def build_kemono_user_by_kwd(no_creator=False, **kwargs):
    from kemonobakend.database.model_builder import build_kemono_creator_by_user
    
    if link_accounts := kwargs.pop('link_accounts', []):
        link_accounts: list[dict]
        if isinstance(link_accounts, list):
            link_accounts_str = json_dumps(link_accounts)
        elif isinstance(link_accounts, str):
            link_accounts_str = link_accounts
        else:
            raise TypeError("link_accounts must be a list or a string")
    else:
        link_accounts_str = "[]"
    
    if not (hash_id := kwargs.get('hash_id')):
        user_id = kwargs.pop("id")
        kwargs["user_id"] = user_id
        hash_id = user_hash_id_func(user_id, kwargs.get("service"))
        kwargs["hash_id"] = hash_id
    kemono_user = KemonoUserCreate(link_accounts=link_accounts_str, **kwargs)
    if not no_creator:
        creator = build_kemono_creator_by_user(kemono_user, link_accounts)
        kemono_user.kemono_creator = creator
    return kemono_user