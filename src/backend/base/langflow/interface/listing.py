from typing_extensions import override

from langflow.services.deps import get_settings_service
from langflow.utils.lazy_load import LazyLoadDictBase


class AllTypesDict(LazyLoadDictBase):
    def __init__(self) -> None:
        self._all_types_dict = None

    def _build_dict(self):
        langchain_types_dict = self.get_type_dict()
        return {
            **langchain_types_dict,
            "Custom": ["Custom Tool", "Python Function"],
        }

    @override
    def get_type_dict(self):
        from langflow.interface.components import get_all_types_dict

        settings_service = get_settings_service()
        return get_all_types_dict(settings_service.settings.components_path)


lazy_load_dict = AllTypesDict()
