from kemonobakend.database.models import FormatterParamsCreate
from kemonobakend.kemono.builtins import formatter_params_hash_id_func
from kemonobakend.utils import json_dumps

def build_formatter_param(formatter_name, version = "v1.0.0", **params):
    return FormatterParamsCreate(
        hash_id = formatter_params_hash_id_func(formatter_name, params),
        formatter_name =formatter_name,
        version = version,
        param_json=json_dumps(params)
    )