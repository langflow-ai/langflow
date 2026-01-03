
from langflow.services.publish.service import IDType, VersionType

MISSING_BUCKET_NAME_MSG = "Publish backend bucket name not specified"
MISSING_USER_OR_FLOW_ID_MSG = "user_id and flow_id are required."
MISSING_USER_OR_PROJECT_ID_MSG = "user_id and project_id are required."
MISSING_VERSION_ERR_MSG = "Version not specified"

def require_bucket_name(bucket_name: str | None):
    if bucket_name is None:
        raise ValueError(MISSING_BUCKET_NAME_MSG)


def require_ids(id1: IDType, id2: IDType, error_msg: str):
    if not (id1 and id2):
        raise ValueError(error_msg)


def require_version(version: VersionType):
    if version is None:
        raise ValueError(MISSING_VERSION_ERR_MSG)


def validate_all(
    bucket_name: str | None,
    user_id: IDType,
    item_id: IDType,
    id_err_msg: str,
    version: VersionType
    ):
    require_bucket_name(bucket_name)
    require_ids(user_id, item_id, id_err_msg)
    require_version(version)
