import fnmatch
import os
import tempfile
from typing import Any

import boto3

from langflow.base.data.utils import parse_text_file_to_data
from langflow.custom import Component
from langflow.io import (
    Output,
    SecretStrInput,
    StrInput,
)
from langflow.schema import Data


class S3BucketRetrieverComponent(Component):
    """A component for retrieving data from an S3 bucket.

    Attributes:
        display_name (str): The display name of the component.
        description (str): A brief description of the component.
        icon (str): The icon representing the component.
        name (str): The name of the component.
        inputs (list): A list of input configurations for the component.
        outputs (list): A list of output configurations for the component.

    Methods:
        _s3_client() -> Any:
            Downloads the specified object from the S3 bucket to a temporary file and returns the file path.
        as_data() -> Data:
            Converts the input value to a Data object by downloading the object from the S3 bucket and parsing it.
    """

    display_name = "S3 Bucket Retreiver"
    description = "Reads from S3 bucket."
    icon = "Globe"
    name = "s3bucketretreiver"

    inputs = [
        SecretStrInput(
            name="aws_access_key_id",
            display_name="AWS Access Key ID",
            required=True,
            password=True,
            info="AWS Access key ID.",
        ),
        SecretStrInput(
            name="aws_secret_access_key",
            display_name="AWS Secret Key",
            required=True,
            password=True,
            info="AWS Secret Key.",
        ),
        StrInput(
            name="bucket_name",
            display_name="Bucket Name",
            info="Enter the name of the bucket.",
            advanced=False,
        ),
        StrInput(
            name="s3_prefix",
            display_name="Prefix",
            info="S3 Bucket Prefix.",
            advanced=False,
        ),
        StrInput(
            name="object_name",
            display_name="Object Name",
            info="Object name or wildcard for download.",
            advanced=False,
        ),
    ]

    outputs = [
        Output(display_name="Retrieve files from S3", name="data", method="retrieve_files"),
    ]

    def _s3_client(self) -> Any:
        """Creates and returns an S3 client using the provided AWS access key ID and secret access key.

        Returns:
            Any: A boto3 S3 client instance.
        """
        return boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        )

    def retrieve_files(self) -> Data:
        # List objects with the specified prefix
        response = self._s3_client().list_objects_v2(Bucket=self.bucket_name, Prefix=self.s3_prefix)
        if "Contents" not in response:
            self.log(f"No objects found with prefix {self.s3_prefix}")
            return []

        # Filter objects based on the wildcard pattern
        matching_keys = [obj["Key"] for obj in response["Contents"] if fnmatch.fnmatch(obj["Key"], self.object_name)]
        self.log(f"Found {len(matching_keys)} objects matching {self.object_name}")

        # Download each matching object
        data_list = []
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download each matching object
            for key in matching_keys:
                file_name = os.path.join(temp_dir, os.path.basename(key))
                self._s3_client().download_file(self.bucket_name, key, file_name)
                data_list.append(parse_text_file_to_data(file_name, silent_errors=True))
        return data_list
