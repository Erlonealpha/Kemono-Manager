from kemonobakend.database.models import KemonoFile, KemonoFileCreate, KemonoAttachment
from kemonobakend.kemono.builtins import file_hash_id_func

def build_kemono_file_by_kwd(
    formatter_name,
    user_hash_id, 
    post_hash_id, 
    attachment_hash_id,
    idx, sha256, 
    save_path, root, folder, file_name, 
    file_size = None, file_type = None, 
):
    hash_id = file_hash_id_func(save_path, sha256)
    return KemonoFile(
        formatter_name=formatter_name,
        hash_id=hash_id,
        user_hash_id=user_hash_id, post_hash_id=post_hash_id, attachment_hash_id=attachment_hash_id,
        idx=idx, sha256=sha256, save_path=save_path, root=root, folder=folder, 
        file_name=file_name, file_size=file_size, file_type=file_type
    )

def build_kemono_file_by_attachment(formatter_name, attachment: KemonoAttachment, save_path, root, folder, file_name, file_size = None, file_type = None):
    hash_id = file_hash_id_func(save_path, attachment.sha256 or attachment.path)
    return KemonoFile(
        formatter_name=formatter_name,
        hash_id=hash_id,
        user_hash_id=attachment.user_hash_id, post_hash_id=attachment.post_hash_id, attachment_hash_id=attachment.hash_id,
        idx=attachment.idx, sha256=attachment.sha256, save_path=save_path, root=root, folder=folder,
        file_name=file_name, file_size=file_size or attachment.size, file_type=file_type
    )
