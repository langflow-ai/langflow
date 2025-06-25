from langflow.custom.custom_component.component import Component
from langflow.services.deps import get_shared_component_cache_service


class ComponentWithCache(Component):
    def __init__(self, **data) -> None:
        super().__init__(**data)
        self._shared_component_cache = get_shared_component_cache_service()
