from pathlib import Path
from typing import Any

from langflow.custom.custom_component.component import Component
from langflow.io import (
    BoolInput,
    DropdownInput,
    HandleInput,
    Output,
    SecretStrInput,
    StrInput,
)


class S3BucketUploaderComponent(Component):
    """S3BucketUploaderComponent is a component responsible for uploading files to an S3 bucket.

    It provides two strategies for file upload: "By Data" and "By File Name". The component
    requires AWS credentials and bucket details as inputs and processes files accordingly.

    Attributes:
        display_name (str): The display name of the component.
        description (str): A brief description of the components functionality.
        icon (str): The icon representing the component.
        name (str): The internal name of the component.
        inputs (list): A list of input configurations required by the component.
        outputs (list): A list of output configurations provided by the component.

    Methods:
        process_files() -> None:
            Processes files based on the selected strategy. Calls the appropriate method
            based on the strategy attribute.
        process_files_by_data() -> None:
            Processes and uploads files to an S3 bucket based on the data inputs. Iterates
            over the data inputs, logs the file path and text content, and uploads each file
            to the specified S3 bucket if both file path and text content are available.
        process_files_by_name() -> None:
            Processes and uploads files to an S3 bucket based on their names. Iterates through
            the list of data inputs, retrieves the file path from each data item, and uploads
            the file to the specified S3 bucket if the file path is available. Logs the file
            path being uploaded.
        _s3_client() -> Any:
            Creates and returns an S3 client using the provided AWS access key ID and secret
            access key.

        Please note that this component requires the boto3 library to be installed. It is designed
        to work with File and Director components as inputs
    """

    display_name = "S3 Bucket Uploader"
    description = "Uploads files to S3 bucket."
    icon = "Amazon"
    name = "s3bucketuploader"

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
        DropdownInput(
            name="strategy",
            display_name="Strategy for file upload",
            options=["Store Data", "Store Original File"],
            value="By Data",
            info=(
                "Choose the strategy to upload the file. By Data means that the source file "
                "is parsed and stored as LangFlow data. By File Name means that the source "
                "file is uploaded as is."
            ),
        ),
        HandleInput(
            name="data_inputs",
            display_name="Data Inputs",
            info="The data to split.",
            input_types=["Data"],
            is_list=True,
            required=True,
        ),
        StrInput(
            name="s3_prefix",
            display_name="S3 Prefix",
            info="Prefix for all files.",
            advanced=True,
        ),
        BoolInput(
            name="strip_path",
            display_name="Strip Path",
            info="Removes path from file path.",
            required=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Writes to AWS Bucket", name="data", method="process_files"),
    ]

    def process_files(self) -> None:
        """Process files based on the selected strategy.

        This method uses a strategy pattern to process files. The strategy is determined
        by the `self.strategy` attribute, which can be either "By Data" or "By File Name".
        Depending on the strategy, the corresponding method (`process_files_by_data` or
        `process_files_by_name`) is called. If an invalid strategy is provided, an error
        is logged.

        Returns:
            None
        """
        strategy_methods = {
            "Store Data": self.process_files_by_data,
            "Store Original File": self.process_files_by_name,
        }
        strategy_methods.get(self.strategy, lambda: self.log("Invalid strategy"))()

    def process_files_by_data(self) -> None:
        """Processes and uploads files to an S3 bucket based on the data inputs.

        This method iterates over the data inputs, logs the file path and text content,
        and uploads each file to the specified S3 bucket if both file path and text content
        are available.

        Args:
            None

        Returns:
            None
        """
        for data_item in self.data_inputs:
            file_path = data_item.data.get("file_path")
            text_content = data_item.data.get("text")

            if file_path and text_content:
                self._s3_client().put_object(
                    Bucket=self.bucket_name, Key=self._normalize_path(file_path), Body=text_content
                )

    def process_files_by_name(self) -> None:
        """Processes and uploads files to an S3 bucket based on their names.

        Iterates through the list of data inputs, retrieves the file path from each data item,
        and uploads the file to the specified S3 bucket if the file path is available.
        Logs the file path being uploaded.

        Returns:
            None
        """
        for data_item in self.data_inputs:
            file_path = data_item.data.get("file_path")
            self.log(f"Uploading file: {file_path}")
            if file_path:
                self._s3_client().upload_file(file_path, Bucket=self.bucket_name, Key=self._normalize_path(file_path))

    def _s3_client(self) -> Any:
        """Creates and returns an S3 client using the provided AWS access key ID and secret access key.

        Returns:
            Any: A boto3 S3 client instance.
        """
        try:
            import boto3
        except ImportError as e:
            msg = "boto3 is not installed. Please install it using `uv pip install boto3`."
            raise ImportError(msg) from e

        return boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        )

    def _normalize_path(self, file_path) -> str:
        """Process the file path based on the s3_prefix and path_as_prefix.

        Args:
            file_path (str): The original file path.
            s3_prefix (str): The S3 prefix to use.
            path_as_prefix (bool): Whether to use the file path as the S3 prefix.

        Returns:
            str: The processed file path.
        """
        prefix = self.s3_prefix
        strip_path = self.strip_path
        processed_path: str = file_path

        if strip_path:
            # Filename only
            processed_path = Path(file_path).name

        # Concatenate the s3_prefix if it exists
        if prefix:
            processed_path = str(Path(prefix) / processed_path)

        return processed_path
