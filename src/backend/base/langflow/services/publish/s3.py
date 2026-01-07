from __future__ import annotations

import json
from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.services.publish.schema import PublishedFlowMetadata
from langflow.services.publish.service import PublishService
from langflow.services.publish.utils import (
    INVALID_KEY_MSG,
    IDType,
    IDTypeStrict,
    compute_dict_hash,
    parse_flow_key,
    require_all_ids,
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

    def _get_client(self):
        return self.session.client("s3")

    async def get_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        key: PublishedFlowMetadata,
        ) -> str | None:
        validate_all(
            bucket_name=self.bucket_name,
            user_id=user_id,
            item_id=flow_id,
            item_type="flow",
            )

        # construct object key
        publish_key = self._flow_key(
            user_id=user_id,
            flow_id=flow_id,
            **key.model_dump(),
        )

        self._flow_key_validate_owner(user_id, flow_id, publish_key)

        async with self._get_client() as client:
            obj = await client.get_object(Bucket=self.bucket_name, Key=publish_key)
            return (await obj["Body"].read()).decode("utf-8")

    async def put_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        flow_blob: dict,
        publish_tag: str | None
    ) -> PublishedFlowMetadata:
        validate_all(
            bucket_name=self.bucket_name,
            user_id=user_id,
            item_id=flow_id,
            item_type="flow",
            )
        require_valid_flow(flow_blob)

        version_id = to_alnum_string(publish_tag) or compute_dict_hash(flow_blob)
        timestamp = utc_now_strf()
        flow_name = flow_blob["name"]

        key = self._flow_key(
            user_id=user_id,
            flow_id=flow_id,
            flow_name=flow_name,
            version_id=version_id,
            timestamp=timestamp
            )

        print("KEY: ", key)
        async with self._get_client() as client:
            await client.put_object(
                IfNoneMatch="*", # prevent creating new s3 versions if the object already exists
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(flow_blob),
                ContentType="application/json",
            )


        logger.info(f"Published flow with key s3://{self.bucket_name}/{key}")
        return PublishedFlowMetadata(version_id=version_id, timestamp=timestamp, flow_name=flow_name)

    async def delete_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        key: PublishedFlowMetadata,
    ) -> None:
        validate_all(
            bucket_name=self.bucket_name,
            user_id=user_id,
            item_id=flow_id,
            item_type="flow",
            )

        # Reconstruct key from components
        publish_key = self._flow_key(user_id=user_id, flow_id=flow_id, **key.model_dump())

        self._flow_key_validate_owner(user_id, flow_id, publish_key)

        async with self._get_client() as client:
            await client.delete_object(Bucket=self.bucket_name, Key=publish_key)

        logger.info(f"Deleted published flow with key s3://{self.bucket_name}/{publish_key}")


    async def list_flow_versions(
        self,
        user_id: IDType,
        flow_id: IDType,
        ) -> list[PublishedFlowMetadata] | None:
        """List published versions of the given flow."""
        require_all_ids(user_id=user_id, item_id=flow_id, item_type="flow")
        versions = []
        async with self._get_client() as client:
            paginator = client.get_paginator("list_objects_v2")
            pages = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=self._flow_key_prefix(user_id, flow_id)
            )
            # print(pages)
            async for page in pages:
                versions.extend(parse_flow_key(obj["Key"]) for obj in page["Contents"])
            # print(mylist)
            return versions

    # TODO: Get rid of timestamp, use s3 LastModified
    # + policy to enforce conditional writes (require if-none-match=="*")
    # such that LastModified remains tied to creation date.
    def _flow_key(
        self,
        user_id: IDTypeStrict,
        flow_id: IDTypeStrict,
        flow_name: str,
        version_id: str,
        timestamp: str,
        ) -> str:
        return (
            # note: prefix already contains the / at the end
            f"{self._flow_key_prefix(user_id, flow_id)}"
            f"/id={version_id}"
            f"/timestamp={timestamp}"
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

    # note: self.prefix already contains a trailing slash
    def _flow_key_prefix(self, user_id: IDTypeStrict, flow_id: IDTypeStrict):
        """Return the key prefix used for publishing flows (without trailing slash)."""
        return f"{self.prefix}{user_id!s}/flows/{flow_id!s}/versions"

    # def _flow_key_deploy_prefix(self, user_id: IDTypeStrict, flow_id: IDTypeStrict):
    #     """Return the key prefix used for deploying flows (without trailing slash)."""
    #     return f"{self.deploy_prefix}{user_id!s}/flows/{flow_id!s}/versions"

