from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.services.publish.service import IDType, IDTypeStrict, PublishService
from langflow.services.publish.utils import (
    INVALID_KEY_MSG,
    compute_dict_hash,
    require_valid_flow,
    to_alnum_string,
    utc_now_strf,
    validate_all,
)

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class S3PublishService(PublishService):
    def __init__(self, settings_service: SettingsService):
        super().__init__(settings_service)
        self.bucket_name = settings_service.settings.publish_backend_bucket_name
        self.session = None

        try:
            import aioboto3
            self.session = aioboto3.Session()
        except ImportError:
            logger.warning("aioboto3 not installed. S3 Publish service will not work.")

    async def _get_client(self):
        return self.session.client("s3")

    async def get_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        publish_key: str
        ) -> str | None:
        validate_all(
            bucket_name=self.bucket_name,
            user_id=user_id,
            item_id=flow_id,
            item_type="flow",
            )
        self._flow_key_validate_owner(flow_id, user_id, publish_key)

        async with self._get_client() as client:
            response = await client.get_object(Bucket=self.bucket_name, Key=publish_key)
            content = await response["Body"].read()
            return content.decode("utf-8")

    async def put_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        flow_blob: dict,
        publish_tag: str | None
    ) -> str | None:
        validate_all(
            bucket_name=self.bucket_name,
            user_id=user_id,
            item_id=flow_id,
            item_type="flow",
            )
        require_valid_flow(flow_blob)

        key = self._flow_key(
            user_id=user_id,
            flow_id=flow_id,
            flow_name=flow_blob["name"],
            # version id is user provided tag or falls back to sha256 of flow blob
            version_id=to_alnum_string(publish_tag) or compute_dict_hash(flow_blob)
            )

        print("KEY: ", key)
        # async with self._get_client() as client:
        #     await client.put_object(
        #         IfNoneMatch="*", # prevent creating new s3 versions if the object already exists
        #         Bucket=self.bucket_name,
        #         Key=key,
        #         Body=json.dumps(flow_blob),
        #         ContentType="application/json",
        #     )


        logger.info(f"Published flow with key s3://{self.bucket_name}/{key}")
        return key

    async def delete_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        publish_key: IDType,
    ) -> str | None:
        validate_all(
            bucket_name=self.bucket_name,
            user_id=user_id,
            item_id=flow_id,
            item_type="flow",
            )
        self._flow_key_validate_owner(flow_id, user_id, publish_key)

        async with self._get_client() as client:
            await client.delete_object(Bucket=self.bucket_name, Key=publish_key)

        logger.info(f"Deleted published flow with key s3://{self.bucket_name}/{publish_key}")
        return publish_key

    def _flow_key(
        self,
        user_id: IDTypeStrict,
        flow_id: IDTypeStrict,
        flow_name: str,
        version_id: str,
        ) -> str:
        return (
            # note: prefix already contains the / at the end
            f"{self._flow_key_prefix(user_id, flow_id)}versions"
            f"/id={version_id!s}"
            f"/timestamp={utc_now_strf()}"
            f"/flow_name={flow_name}"
            )

    def _flow_key_validate_owner(
        self,
        user_id: IDTypeStrict,
        flow_id: IDTypeStrict,
        flow_key: str | None,
        ) -> str:
        """Raises a ValueError if the key is None, empty, or does not match provided user and flow ids."""
        if not (flow_key and flow_key.startswith(self._flow_key_prefix(user_id, flow_id))):
            raise ValueError(INVALID_KEY_MSG)

    def _flow_key_prefix(self, user_id: IDTypeStrict, flow_id: IDTypeStrict):
        """Return the key prefix used for publishing flows (with trailing slash)."""
        # note: prefix already contains the / at the end
        return f"{self.prefix}{user_id!s}/flows/{flow_id!s}/"

    def _flow_key_deploy_prefix(self, user_id: IDTypeStrict, flow_id: IDTypeStrict):
        """Return the key prefix used for deploying flows (with trailing slash)."""
        # note: prefix already contains the / at the end
        return f"{self.deploy_prefix}{user_id!s}/flows/{flow_id!s}/"
