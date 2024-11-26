from kemonobakend.database.models import KemonoUserCreate, KemonoCreatorCreate
from kemonobakend.kemono.builtins import creator_hash_id_func, user_hash_id_func, select_public_user
from kemonobakend.utils import json_loads, json_dumps

def build_kemono_creator(raw_user_data: dict, link_accounts: list[dict], creators: dict):
    from kemonobakend.database.model_builder import build_kemono_user_by_creator
    
    def link_account_to_user(hash_id):
        if hash_id == raw_hash_id:
            user = raw_user_data.copy()
            link_accounts_ = link_accounts
        else:
            user = creators.get(hash_id)
            if user is None:
                raise ValueError(f"User with hash_id {hash_id} not found in creators")
            link_accounts_ = [link_account for link_account in all_link_accounts_map.values() if link_account.get("id") != user.get("id")]
        user["relation_id"] = relation_id
        user["link_accounts"] = json_dumps(link_accounts_)
        return user
    
    raw_hash_id = user_hash_id_func(raw_user_data.get("id"), raw_user_data.get("service"))
    relation_id = link_accounts[0].get("relation_id") if len(link_accounts) > 0 else None
    _raw_user_data = raw_user_data.copy()
    _raw_user_data.pop("favorited", None)
    _raw_user_data["relation_id"] = relation_id
    all_link_accounts_map = {raw_hash_id: _raw_user_data}
    all_link_accounts_map.update({user_hash_id_func(user.get("id"), user.get("service")): user for user in link_accounts})
    
    all_users = [link_account_to_user(hash_id) for hash_id in all_link_accounts_map.keys()]
    pub_user = select_public_user(all_users)
    pub_id = pub_user["id"]
    pub_service = pub_user["service"]
    pub_name = pub_user["name"]
    kemono_creator = KemonoCreatorCreate(
        hash_id = creator_hash_id_func(pub_id, pub_name),
        name = pub_name,
        name_from = pub_service,
        public_user_hash_id = user_hash_id_func(pub_id, pub_service),
        relation_id = relation_id
    )
    for user in all_users:
        user["public_name"] = pub_name
        user["creator_hash_id"] = kemono_creator.hash_id
    kemono_creator.kemono_users = [build_kemono_user_by_creator(kemono_creator, **user) for user in all_users]
    return kemono_creator

def build_kemono_creator_by_user(kemono_user: KemonoUserCreate, link_accounts: list[dict] = None, no_users: bool = False):
    from kemonobakend.database.model_builder import build_kemono_user_by_creator
    
    all_users = link_accounts.copy()
    all_users.append(kemono_user.model_dump())
    pub_user = select_public_user(all_users)
    id = pub_user["id"]
    service = pub_user["service"]
    name = pub_user["name"]
    kemono_creator = KemonoCreatorCreate(
        hash_id=creator_hash_id_func(id, name),
        name=name,
        name_from=service,
        public_user_hash_id=user_hash_id_func(id, service),
    )
    if not no_users:
        if link_accounts is None:
            link_accounts = json_loads(kemono_user.link_accounts)
        all_users.pop(-1)
        kemono_creator.kemono_users = [build_kemono_user_by_creator(kemono_creator, **user) for user in all_users]
        kemono_user.kemono_creator = kemono_creator
        kemono_creator.kemono_users.append(kemono_user)
    return kemono_creator
