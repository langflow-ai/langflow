from uuid import UUID

from sqlmodel import select

from langflow.api.utils import DbSession
from langflow.helpers.utils import (
    get_uuid,
    require_publish_provider,
    require_user_and_item_ids,
    require_user_id,
)
from langflow.services.database.models.flow_publish import FlowPublish
from langflow.services.database.models.flow_publish.model import PublishProviderEnum, PublishStateEnum
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.deps import session_scope
from langflow.services.publish.service import IDType

FLOW_PUBLISH_NOT_FOUND_ERROR_MSG = "Flow publish data not found."


async def get_flow_publish(
    *,
    user_id: IDType,
    publish_id: IDType,
) -> dict:
    require_user_and_item_ids(user_id, publish_id, "publish")

    user_uuid = get_uuid(user_id)
    publish_uuid = get_uuid(publish_id)

    try:
        async with session_scope() as session:
            db_flow = (
                await session.exec(
                    select(FlowPublish).where(FlowPublish.user_id == user_uuid).where(FlowPublish.id == publish_uuid)
                )
            ).one()
    except Exception as e:
        msg = f"Failed to fetch flow version: {e!s}"
        raise ValueError(msg) from e

    if not db_flow:
        raise ValueError(FLOW_PUBLISH_NOT_FOUND_ERROR_MSG)

    return db_flow.model_dump()


async def create_flow_publish(
    *,
    session: DbSession | None,
    user_id: IDType,
    flow_version: FlowVersion,
    publish_provider: str,
) -> FlowPublish:
    require_user_id(user_id)
    require_publish_provider(publish_provider)
    # should we validate flow_version?

    user_uuid = get_uuid(user_id)

    if session:
        return await _create_flow_publish(
            session=session,
            user_id=user_uuid,
            flow_version=flow_version,
            publish_provider=publish_provider,
        )
    async with session_scope() as _session:
        return await _create_flow_publish(
            session=_session, user_id=user_uuid, flow_version=flow_version, publish_provider=publish_provider
        )


async def _create_flow_publish(
    *,
    session: DbSession,
    user_id: UUID,
    flow_version: FlowVersion,
    publish_provider: str,
) -> FlowPublish:
    try:
        flow_publish = FlowPublish(
            user_id=user_id,
            flow_id=flow_version.flow_id,
            flow_version_id=flow_version.id,
            publish_state=PublishStateEnum(PublishStateEnum.PENDING),
            publish_provider=PublishProviderEnum(publish_provider),
        )
        session.add(flow_publish)
    except Exception as e:
        msg = f"Failed to publish flow: {e!s}"
        raise ValueError(msg) from e

    return flow_publish
