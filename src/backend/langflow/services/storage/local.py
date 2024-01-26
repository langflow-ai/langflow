from pathlib import Path

from platformdirs import user_data_dir

from .service import StorageService


class LocalStorageService(StorageService):
    def __init__(self, session_service):
        super().__init__(session_service)
        self.data_dir = user_data_dir("langflow", "langflow")

        self.set_ready()

    def save_file(self, folder: str, file_name: str, data):
        folder_path = Path(f"{self.data_dir}/{folder}")
        folder_path.mkdir(parents=True, exist_ok=True)
        with open(f"{self.data_dir}/{folder}/{file_name}", "w") as f:
            f.write(data)

    def get_file(self, folder: str, file_name: str):
        with open(f"{self.data_dir}/{folder}/{file_name}", "r") as f:
            return f.read()

    def list_files(self, folder: str):
        folder_path = Path(f"{self.data_dir}/{folder}")
        return [file.name for file in folder_path.iterdir() if file.is_file()]

    def delete_file(self, folder: str, file_name: str):
        Path(f"{self.data_dir}/{folder}/{file_name}").unlink()

    def teardown(self):
        pass
