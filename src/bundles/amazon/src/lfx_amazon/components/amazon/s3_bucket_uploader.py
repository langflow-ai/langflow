from pathlib import Path
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DropdownInput,
    HandleInput,
    Output,
    SecretStrInput,
    StrInput,
)
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class S3BucketUploaderComponent(Component):
    """S3BucketUploaderComponent is a component responsible for uploading files to an S3 bucket.

    It provides two strategies for file upload: "Store Data" and "Store Original File". The component
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
            over the data inputs and uploads each file's text content to the specified S3
            bucket. An input without a file path or text raises an error.
        process_files_by_name() -> None:
            Processes and uploads files to an S3 bucket based on their names. Iterates through
            the list of data inputs, retrieves the file path from each data item, and uploads
            the file to the specified S3 bucket. An input without a file path raises an error.
        _s3_client() -> Any:
            Creates and returns an S3 client using the provided AWS access key ID and secret
            access key.

        Please note that this component requires the boto3 library to be installed. It is designed
        to work with File and Directory components as inputs
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
            value="Store Data",
            info=(
                "Store Data uploads the parsed text content of each file. "
                "Store Original File uploads each source file as is."
            ),
        ),
        HandleInput(
            name="data_inputs",
            display_name="Data Inputs",
            info="Files or file data to upload.",
            input_types=["Data", "JSON", "DataFrame", "Table", "Message"],
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
        by the `self.strategy` attribute, which can be either "Store Data" or "Store Original File".
        Depending on the strategy, the corresponding method (`process_files_by_data` or
        `process_files_by_name`) is called. An invalid strategy raises an error.

        Returns:
            None
        """
        strategy_methods = {
            "Store Data": self.process_files_by_data,
            "Store Original File": self.process_files_by_name,
        }
        strategy = self.strategy
        if strategy not in strategy_methods:
            msg = f"Invalid S3 upload strategy {strategy!r}. Choose Store Data or Store Original File."
            raise ValueError(msg)
        strategy_methods[strategy]()

    def _file_data_items(self) -> list[Data]:
        """Expand file tables and multi-file Read File messages into individual records."""
        inputs = self.data_inputs
        if not isinstance(inputs, list):
            inputs = [inputs]

        items = []
        for item in inputs:
            if isinstance(item, DataFrame):
                items.extend(item.to_data_list())
            elif isinstance(item, Data):
                source_files = item.data.get("source_files")
                if source_files is None:
                    items.append(item)
                elif isinstance(source_files, list) and source_files:
                    for source_file in source_files:
                        if not isinstance(source_file, dict):
                            msg = "Invalid Read File source_files entry."
                            raise TypeError(msg)
                        items.append(Data(data=source_file))
                else:
                    msg = "Invalid Read File source_files value."
                    raise ValueError(msg)
            else:
                msg = f"Unsupported S3 upload input: {type(item).__name__}"
                raise TypeError(msg)
        return items

    def process_files_by_data(self) -> None:
        """Processes and uploads files to an S3 bucket based on the data inputs.

        This method iterates over the data inputs and uploads each file's text content
        to the specified S3 bucket. An input without a file path or text raises an error.

        Args:
            None

        Returns:
            None
        """
        for data_item in self._file_data_items():
            file_path = data_item.data.get("file_path")
            text_content = data_item.data.get("text")
            if not file_path or text_content is None:
                msg = "Store Data requires each input to contain file_path and text."
                raise ValueError(msg)
            self._s3_client().put_object(
                Bucket=self.bucket_name, Key=self._normalize_path(file_path), Body=text_content
            )

    def process_files_by_name(self) -> None:
        """Processes and uploads files to an S3 bucket based on their names.

        Iterates through the list of data inputs, retrieves the file path from each data item,
        and uploads the file to the specified S3 bucket. An input without a file path
        raises an error.

        Returns:
            None
        """
        for data_item in self._file_data_items():
            file_path = data_item.data.get("file_path")
            if not file_path:
                msg = "Store Original File requires each input to contain file_path."
                raise ValueError(msg)
            self.log(f"Uploading file: {file_path}")
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
