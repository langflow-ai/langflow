from __future__ import annotations

import contextlib
import json
from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.services.publish.service import PublishService

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

    def _flow_version_key(self, user_id: str, flow_id: str, version_id: str) -> str:
        return f"{self.prefix}{user_id}/flow/{flow_id}/versions/_{version_id}.json"

    def _project_version_key(self, user_id: str, project_id: str, version_id: str) -> str:
        return f"{self.prefix}{user_id}/project/{project_id}/versions/_{version_id}.json"

    async def publish_flow(
        self,
        user_id: str,
        flow_id: str,
        flow_data: str,
        version_id: str,
    ) -> str | None:
        if not self.bucket_name:
            msg = "Publish backend bucket name is not configured"
            raise ValueError(msg)

        key = self._flow_version_key(user_id, flow_id, version_id)

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

    async def get_flow(
        self,
        user_id: str,
        flow_id: str,
        version_id: str,
    ) -> str | None:
        key = self._flow_version_key(user_id, flow_id, version_id)

        async with self._get_client() as client:
            try:
                response = await client.get_object(Bucket=self.bucket_name, Key=key)
                content = await response["Body"].read()
                return content.decode("utf-8")
            except Exception as e:
                logger.error(f"Error fetching flow {flow_id}: {e}")
                raise

    async def publish_project(
        self,
        user_id: str,
        project_id: str,
        manifest: dict,
        version_id: str,
    ) -> str | None:
        if not self.bucket_name:
            msg = "Publish backend bucket name is not configured"
            raise ValueError(msg)

        key = self._project_version_key(user_id, project_id, version_id)

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
