from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.helpers.flow_version import FLOW_NOT_FOUND_ERROR_MSG
from langflow.services.publish.service import IDType, IDTypeStrict, PublishService, VersionType
from langflow.services.publish.utils import (
    MISSING_USER_OR_FLOW_ID_MSG,
    MISSING_USER_OR_PROJECT_ID_MSG,
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

    @contextlib.asynccontextmanager
    async def _get_client(self):
        if not self.session:
            msg = "aioboto3 is not installed"
            raise ImportError(msg)

        async with self.session.client("s3") as client:
            yield client

    def _flow_version_key(self, user_id: IDTypeStrict, flow_id: IDTypeStrict, version: IDTypeStrict) -> str:
        return f"{self.prefix}{user_id!s}/flows/{flow_id!s}/versions/_{version!s}.json"

    def _project_version_key(self, user_id: IDTypeStrict, project_id: IDTypeStrict, version: IDTypeStrict) -> str:
        return f"{self.prefix}{user_id!s}/projects/{project_id!s}/versions/_{version!s}.json"

    async def get_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        version: VersionType = None,
    ) -> str | None:
        validate_all(self.bucket_name, user_id, flow_id, MISSING_USER_OR_FLOW_ID_MSG, version)

        key = self._flow_version_key(user_id, flow_id, version)

        async with self._get_client() as client:
            try:
                response = await client.get_object(Bucket=self.bucket_name, Key=key)
                content = await response["Body"].read()
                return content.decode("utf-8")
            except Exception as e:
                logger.error(f"Error fetching flow {flow_id}: {e}")
                raise

    async def put_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        flow_data: str,
        version: VersionType,
    ) -> str | None:
        validate_all(self.bucket_name, user_id, flow_id, MISSING_USER_OR_FLOW_ID_MSG, version)

        key = self._flow_version_key(user_id, flow_id, version)

        async with self._get_client() as client:
            await client.put_object(
                IfNoneMatch="*", # prevent creating new s3 versions if the object already exists
                Bucket=self.bucket_name,
                Key=key,
                Body=flow_data,
                ContentType="application/json",
            )

        logger.info(f"Published flow {flow_id} to s3://{self.bucket_name}/{key}")
        return key

    async def delete_flow(
        self,
        user_id: IDType,
        flow_id: IDType,
        flow_data: str,
        version: VersionType,
    ) -> str | None:
        validate_all(self.bucket_name, user_id, flow_id, MISSING_USER_OR_FLOW_ID_MSG, version)

        key = self._flow_version_key(user_id, flow_id, version)

        async with self._get_client() as client:
            await client.put_object(
                IfNoneMatch="*", # prevent creating new s3 versions if the object already exists
                Bucket=self.bucket_name,
                Key=key,
                Body=flow_data,
                ContentType="application/json",
            )

        logger.info(f"Published flow {flow_id} to s3://{self.bucket_name}/{key}")
        return key

    async def get_project(
        self,
        user_id: IDType,
        project_id: IDType,
        manifest: dict,
        version: VersionType,
    ) -> str | None:
        validate_all(self.bucket_name, user_id, project_id, FLOW_NOT_FOUND_ERROR_MSG, version)

        key = self._project_version_key(user_id, project_id, version)

        # Serialize manifest to bytes
        project_data = json.dumps(manifest).encode("utf-8")

        async with self._get_client() as client:
            await client.put_object(
                IfNoneMatch="*", # prevent creating new s3 versions if the object already exists
                Bucket=self.bucket_name,
                Key=key,
                Body=project_data,
                ContentType="application/json",
            )

        logger.info(f"Published project {project_id} to s3://{self.bucket_name}/{key}")
        return key

    async def put_project(
        self,
        user_id: IDType,
        project_id: IDType,
        manifest: dict,
        version: VersionType,
    ) -> str | None:
        validate_all(self.bucket_name, user_id, project_id, MISSING_USER_OR_PROJECT_ID_MSG, version)

        key = self._project_version_key(user_id, project_id, version)

        # Serialize manifest to bytes
        project_data = json.dumps(manifest).encode("utf-8")

        async with self._get_client() as client:
            await client.put_object(
                IfNoneMatch="*", # prevent creating new s3 versions if the object already exists
                Bucket=self.bucket_name,
                Key=key,
                Body=project_data,
                ContentType="application/json",
            )

        logger.info(f"Published project {project_id} to s3://{self.bucket_name}/{key}")
        return key

    async def delete_project(
        self,
        user_id: IDType,
        project_id: IDType,
        version: VersionType,
    ) -> str | None:
        validate_all(self.bucket_name, user_id, project_id, FLOW_NOT_FOUND_ERROR_MSG, version)

        key = self._project_version_key(user_id, project_id, version)

        async with self._get_client() as client:
            await client.delete_object(
                IfNoneMatch="*", # prevent creating new s3 versions if the object already exists
                Bucket=self.bucket_name,
                Key=key,
            )

        logger.info(f"Published project {project_id} to s3://{self.bucket_name}/{key}")
        return key
