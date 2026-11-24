from typing_extensions import override

from lfx.services.deps import get_settings_service
from lfx.utils.lazy_load import LazyLoadDictBase


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
        # Must stay synchronous: this is reached from the sync `all_types_dict` property during
        # graph build (vertex base_type fallback). Use the sync builder, not the async
        # `get_all_types_dict` (returning its un-awaited coroutine raised
        # "'coroutine' object is not a mapping").
        from lfx.custom.utils import build_custom_components

        settings_service = get_settings_service()
        return build_custom_components(settings_service.settings.components_path)


lazy_load_dict = AllTypesDict()
