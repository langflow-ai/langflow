from __future__ import annotations

import json
from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.services.publish.schema import PublishedFlowMetadata, PublishedProjectMetadata
from langflow.services.publish.service import PublishService
from langflow.services.publish.utils import (
    INVALID_KEY_MSG,
    IDType,
    IDTypeStrict,
    compute_flow_hash,
    compute_project_hash,
    handle_s3_error,
    parse_blob_key,
    require_all_ids,
    require_valid_flow,
    require_valid_project,
    to_alnum_string,
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
            flow_name=key.flow_name,
            version_id=key.version_id,
        )

        self._flow_key_validate_owner(user_id, flow_id, publish_key)

        try:
            async with self._get_client() as client:
                obj = await client.get_object(Bucket=self.bucket_name, Key=publish_key)
                return (await obj["Body"].read()).decode("utf-8")
        except Exception as e: # noqa: BLE001
            handle_s3_error(e, "flow", op="get")

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

        version_id = to_alnum_string(publish_tag) or compute_flow_hash(flow_blob)
        flow_name = flow_blob["name"]

        key = self._flow_key(
            user_id=user_id,
            flow_id=flow_id,
            flow_name=flow_name,
            version_id=version_id,
            )
        try:
            async with self._get_client() as client:
                    await client.put_object(
                        IfNoneMatch="*", # prevent creating new s3 versions if the object already exists
                        Bucket=self.bucket_name,
                        Key=key,
                        Body=json.dumps(flow_blob),
                        ContentType="application/json",
                    )
        except Exception as e: # noqa: BLE001
            handle_s3_error(e, "flow", op="put")

        logger.info(f"Published flow with key s3://{self.bucket_name}/{key}")
        return PublishedFlowMetadata(version_id=version_id, last_modified=None, flow_name=flow_name)

    async def delete_flow(
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

        # Reconstruct key from components
        publish_key = self._flow_key(
            user_id=user_id,
            flow_id=flow_id,
            flow_name=to_alnum_string(key.flow_name),
            version_id=key.version_id,
        )

        self._flow_key_validate_owner(user_id, flow_id, publish_key)
        try:
            async with self._get_client() as client:
                await client.delete_object(Bucket=self.bucket_name, Key=publish_key, IfMatch="*")
        except Exception as e: # noqa: BLE001
            handle_s3_error(e, "flow", op="delete")

        logger.info(f"Deleted published flow with key s3://{self.bucket_name}/{publish_key}")
        return key.version_id

    async def list_flow_versions(
        self,
        user_id: IDType,
        flow_id: IDType,
        ) -> list[PublishedFlowMetadata] | None:
        """List published versions of the given flow."""
        require_all_ids(user_id=user_id, item_id=flow_id, item_type="flow")
        try:
            versions = []
            async with self._get_client() as client:
                paginator = client.get_paginator("list_objects_v2")
                pages = paginator.paginate(
                    Bucket=self.bucket_name,
                    Prefix=self._flow_versions_prefix(user_id, flow_id)
                )
                async for page in pages:
                    if "Contents" not in page:
                        continue
                    versions.extend([
                        parse_blob_key(
                            key=obj["Key"],
                            last_modified=obj["LastModified"],
                            cls=PublishedFlowMetadata,
                        )
                        for obj in page["Contents"]
                    ])
        except Exception as e: # noqa: BLE001
            handle_s3_error(e, "flow", op="list")

        return versions

    async def get_project(
        self,
        user_id: IDType,
        project_id: IDType,
        key: PublishedProjectMetadata,
    ) -> str | None:
        validate_all(
            bucket_name=self.bucket_name,
            user_id=user_id,
            item_id=project_id,
            item_type="project",
        )

        publish_key = self._project_key(
            user_id=user_id,
            project_id=project_id,
            project_name=key.project_name,
            version_id=key.version_id,
        )

        self._project_key_validate_owner(user_id, project_id, publish_key)

        try:
            async with self._get_client() as client:
                obj = await client.get_object(Bucket=self.bucket_name, Key=publish_key)
                return (await obj["Body"].read()).decode("utf-8")
        except Exception as e:  # noqa: BLE001
            handle_s3_error(e, "project", op="get")

    async def put_project(
        self,
        user_id: IDType,
        project_id: IDType,
        project_blob: dict,
        publish_tag: str | None,
    ) -> PublishedProjectMetadata:
        validate_all(
            bucket_name=self.bucket_name,
            user_id=user_id,
            item_id=project_id,
            item_type="project",
        )
        require_valid_project(project_blob)

        version_id = to_alnum_string(publish_tag) or compute_project_hash(project_blob)
        project_name = project_blob["name"]

        key = self._project_key(
            user_id=user_id,
            project_id=project_id,
            project_name=project_name,
            version_id=version_id,
        )
        try:
            async with self._get_client() as client:
                await client.put_object(
                    IfNoneMatch="*",  # prevent creating new s3 versions if the object already exists
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=json.dumps(project_blob),
                    ContentType="application/json",
                )
        except Exception as e:  # noqa: BLE001
            handle_s3_error(e, "project", op="put")

        logger.info(f"Published project with key s3://{self.bucket_name}/{key}")
        return PublishedProjectMetadata(version_id=version_id, last_modified=None, project_name=project_name)

    async def delete_project(
        self,
        user_id: IDType,
        project_id: IDType,
        key: PublishedProjectMetadata,
    ) -> str | None:
        validate_all(
            bucket_name=self.bucket_name,
            user_id=user_id,
            item_id=project_id,
            item_type="project",
        )

        publish_key = self._project_key(
            user_id=user_id,
            project_id=project_id,
            project_name=to_alnum_string(key.project_name),
            version_id=key.version_id,
        )

        self._project_key_validate_owner(user_id, project_id, publish_key)
        try:
            async with self._get_client() as client:
                await client.delete_object(Bucket=self.bucket_name, Key=publish_key, IfMatch="*")
        except Exception as e:  # noqa: BLE001
            handle_s3_error(e, "project", op="delete")

        logger.info(f"Deleted published project with key s3://{self.bucket_name}/{publish_key}")
        return key.version_id

    async def list_project_versions(
        self,
        user_id: IDType,
        project_id: IDType,
    ) -> list[PublishedProjectMetadata] | None:
        """List published versions of the given project."""
        require_all_ids(user_id=user_id, item_id=project_id, item_type="project")
        try:
            versions = []
            async with self._get_client() as client:
                paginator = client.get_paginator("list_objects_v2")
                pages = paginator.paginate(
                    Bucket=self.bucket_name, Prefix=self._project_versions_prefix(user_id, project_id)
                )
                async for page in pages:
                    if "Contents" not in page:
                        continue

                    versions.extend([
                        parse_blob_key(
                            key=obj["Key"],
                            last_modified=obj["LastModified"],
                            cls=PublishedProjectMetadata,
                            )
                        for obj in page["Contents"]
                    ])
        except Exception as e:  # noqa: BLE001
            handle_s3_error(e, "project", op="list")

        return versions

    def _flow_key(
        self,
        user_id: IDTypeStrict,
        flow_id: IDTypeStrict,
        flow_name: str,
        version_id: str,
        ) -> str:
        return (
            f"{self._flow_versions_prefix(user_id, flow_id)}"
            f"/id={version_id}"
            f"/flow_name={flow_name}"
            )

    def _flow_key_validate_owner(
        self,
        user_id: IDTypeStrict,
        flow_id: IDTypeStrict,
        flow_key: str | None,
        ) -> str:
        """Raises a ValueError if the key is None, empty, or does not match provided user and flow ids."""
        if not (flow_key and flow_key.startswith(self._flow_versions_prefix(user_id, flow_id))):
            raise ValueError(INVALID_KEY_MSG)

    # note: self.prefix already contains a trailing slash
    def _flow_versions_prefix(self, user_id: IDTypeStrict, flow_id: IDTypeStrict):
        """Return the versions key prefix used for publishing flows (without trailing slash)."""
        return f"{self.prefix}{user_id!s}/flows/{flow_id!s}/versions"

    def _project_key(
        self,
        user_id: IDTypeStrict,
        project_id: IDTypeStrict,
        project_name: str,
        version_id: str,
    ) -> str:
        return (
            f"{self._project_versions_prefix(user_id, project_id)}"
            f"/id={version_id}"
            f"/project_name={project_name}"
        )

    def _project_key_validate_owner(
        self,
        user_id: IDTypeStrict,
        project_id: IDTypeStrict,
        project_key: str | None,
    ) -> str:
        if not (project_key and project_key.startswith(self._project_versions_prefix(user_id, project_id))):
            raise ValueError(INVALID_KEY_MSG)

    def _project_versions_prefix(self, user_id: IDTypeStrict, project_id: IDTypeStrict):
        return f"{self.prefix}{user_id!s}/projects/{project_id!s}/versions"
