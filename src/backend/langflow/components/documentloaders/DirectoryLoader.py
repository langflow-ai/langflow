from langflow import CustomComponent
from langchain.schema import Document
from langflow.components.documentloaders.FileLoader import loaders_info
import os


class DirectoryLoaderComponent(CustomComponent):
    display_name: str = "Directory Loader"
    description: str = "Generic File Loader"
    beta = True

    def build_config(self):
        loader_options = ["Automatic"] + [
            loader_info["name"] for loader_info in loaders_info
        ]

        file_types = []
        suffixes = []

        for loader_info in loaders_info:
            if "allowedTypes" in loader_info:
                file_types.extend(loader_info["allowedTypes"])
                suffixes.extend([f".{ext}" for ext in loader_info["allowedTypes"]])

        return {
            "directory_path": {
                "display_name": "Directory Path",
                "required": True,
            },
            "loader": {
                "display_name": "Loader",
                "is_list": True,
                "required": True,
                "options": loader_options,
                "value": "Automatic",
            },
            "code": {"show": False},
        }

    def build(self, directory_path: str, loader: str) -> Document:
        # Verifique se o diretório existe
        if not os.path.exists(directory_path):
            raise ValueError(f"Directory not found: {directory_path}")

        # Lista os arquivos no diretório
        files = [
            f
            for f in os.listdir(directory_path)
            if os.path.isfile(os.path.join(directory_path, f))
        ]

        # Determine o loader automaticamente com base nas extensões dos arquivos
        loader_info = None
        if loader == "Automatic":
            for file in files:
                file_type = file.split(".")[-1]
                for info in loaders_info:
                    if "defaultFor" in info and file_type in info["defaultFor"]:
                        loader_info = info
                        break
                if loader_info:
                    break

            if not loader_info:
                raise ValueError(
                    "No default loader found for any file in the directory"
                )

        else:
            for info in loaders_info:
                if info["name"] == loader:
                    loader_info = info
                    break

            if not loader_info:
                raise ValueError(f"Loader {loader} not found in the loader info list")

        loader_import = loader_info["import"]
        module_name, class_name = loader_import.rsplit(".", 1)

        try:
            # Importe o loader dinamicamente
            loader_module = __import__(module_name, fromlist=[class_name])
            loader_instance = getattr(loader_module, class_name)
        except ImportError as e:
            raise ValueError(
                f"Loader {loader} could not be imported\nLoader info:\n{loader_info}"
            ) from e

        results = []
        for file in files:
            file_path = os.path.join(directory_path, file)
            result = loader_instance(file_path=file_path).load()
            results.append(result)

        return results
