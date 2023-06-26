from pydantic import BaseModel
from pydantic.types import PyObject


class Component(BaseModel):
    class_object: PyObject
    documentation: str = ""
    init_function: PyObject = "langflow.interface.initialize.base_init_function"


class ComponentList(BaseModel):
    components: list[Component]

    # make getter and setter for component_names property
    @property
    def component_names(self) -> set[str]:
        return {component.class_object.__name__ for component in self.components}

    # check if name is in components
    def __contains__(self, name: str):
        return name in self.component_names

    # get component by name
    def __getitem__(self, name: str) -> Component:
        for component in self.components:
            if component.class_object.__name__ == name:
                return component
        raise KeyError(f"Component {name} not found")
