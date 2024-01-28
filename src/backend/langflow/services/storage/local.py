from pathlib import Path

from .service import StorageService


class LocalStorageService(StorageService):
    def __init__(self, session_service, settings_service):
        super().__init__(session_service, settings_service)
        self.data_dir = settings_service.settings.CONFIG_DIR

        self.set_ready()

    def save_file(self, flow_id: str, file_name: str, data: bytes):
        folder_path = Path(f"{self.data_dir}/{flow_id}")
        folder_path.mkdir(parents=True, exist_ok=True)
        with open(folder_path / file_name, "wb") as f:
            f.write(data)

    def get_file(self, flow_id: str, file_name: str) -> bytes:
        with open(f"{self.data_dir}/{flow_id}/{file_name}", "rb") as f:
            return f.read()

    def list_files(self, flow_id: str):
        folder_path = Path(f"{self.data_dir}/{flow_id}")
        return [file.name for file in folder_path.iterdir() if file.is_file()]

    def delete_file(self, flow_id: str, file_name: str):
        Path(f"{self.data_dir}/{flow_id}/{file_name}").unlink()

    def teardown(self):
        pass
