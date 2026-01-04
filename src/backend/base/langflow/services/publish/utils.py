
from langflow.services.publish.service import IDType

MISSING_BUCKET_NAME_MSG = "Publish backend bucket name not specified"
MISSING_ALL_ID_MSG = "user_id, {item_type}_id and publish_id are required."

def require_bucket_name(bucket_name: str | None):
    if bucket_name is None or not bucket_name.strip():
        raise ValueError(MISSING_BUCKET_NAME_MSG)


def require_all_ids(
    user_id: IDType,
    item_id: IDType,
    publish_id: IDType,
    item_type: str
    ):
    if not (user_id and item_id and publish_id):
        raise ValueError(MISSING_ALL_ID_MSG.format(item_type=item_type))


def validate_all(
    bucket_name: str | None,
    user_id: IDType,
    item_id: IDType,
    publish_id: IDType,
    item_type: str,
    ):
    require_bucket_name(bucket_name)
    require_all_ids(user_id, item_id, publish_id, item_type)
