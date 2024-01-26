import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .service import StorageService


class S3StorageService(StorageService):
    def __init__(self, session_service):
        super().__init__(session_service)
        self.bucket = "langflow"
        self.s3_client = boto3.client("s3")
        self.set_ready()

    def save_file(self, folder: str, file_name: str, data):
        try:
            self.s3_client.put_object(Bucket=self.bucket, Key=f"{folder}/{file_name}", Body=data)
        except NoCredentialsError:
            raise Exception("Credentials not available for AWS S3.")
        except ClientError as e:
            raise Exception(f"An error occurred: {e}")

    def get_file(self, folder: str, file_name: str):
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=f"{folder}/{file_name}")
            return response["Body"].read()
        except ClientError as e:
            raise Exception(f"An error occurred: {e}")

    def list_files(self, folder: str):
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=folder)
            return [item["Key"] for item in response.get("Contents", []) if "/" not in item["Key"][len(folder) :]]
        except ClientError as e:
            raise Exception(f"An error occurred: {e}")

    def delete_file(self, folder: str, file_name: str):
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=f"{folder}/{file_name}")
        except ClientError as e:
            raise Exception(f"An error occurred: {e}")

    def teardown(self):
        pass
