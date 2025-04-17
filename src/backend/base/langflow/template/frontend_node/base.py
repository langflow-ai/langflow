from collections import defaultdict

from pydantic import BaseModel, field_serializer, model_serializer

from langflow.template.field.base import Output
from langflow.template.template.base import Template


class FrontendNode(BaseModel):
    _format_template: bool = True
    template: Template
    """Template for the frontend node."""
    description: str | None = None
    """Description of the frontend node."""
    icon: str | None = None
    """Icon of the frontend node."""
    is_input: bool | None = None
    """Whether the frontend node is used as an input when processing the Graph.
    If True, there should be a field named 'input_value'."""
    is_output: bool | None = None
    """Whether the frontend node is used as an output when processing the Graph.
    If True, there should be a field named 'input_value'."""
    is_composition: bool | None = None
    """Whether the frontend node is used for composition."""
    base_classes: list[str]
    """List of base classes for the frontend node."""
    name: str = ""
    """Name of the frontend node."""
    display_name: str | None = ""
    """Display name of the frontend node."""
    priority: int | None = None
    """Priority of the frontend node."""
    documentation: str = ""
    """Documentation of the frontend node."""
    minimized: bool = False
    """Whether the frontend node is minimized."""
    custom_fields: dict | None = defaultdict(list)
    """Custom fields of the frontend node."""
    output_types: list[str] = []
    """List of output types for the frontend node."""
    full_path: str | None = None
    """Full path of the frontend node."""
    pinned: bool = False
    """Whether the frontend node is pinned."""
    conditional_paths: list[str] = []
    """List of conditional paths for the frontend node."""
    frozen: bool = False
    """Whether the frontend node is frozen."""
    outputs: list[Output] = []
    """List of output fields for the frontend node."""

    field_order: list[str] = []
    """Order of the fields in the frontend node."""
    beta: bool = False
    """Whether the frontend node is in beta."""
    legacy: bool = False
    """Whether the frontend node is legacy."""
    error: str | None = None
    """Error message for the frontend node."""
    edited: bool = False
    """Whether the frontend node has been edited."""
    metadata: dict = {}
    """Metadata for the component node."""
    tool_mode: bool = False
    """Whether the frontend node is in tool mode."""

    def set_documentation(self, documentation: str) -> None:
        """Sets the documentation of the frontend node."""
        self.documentation = documentation

    @field_serializer("base_classes")
    def process_base_classes(self, base_classes: list[str]) -> list[str]:
        """Removes unwanted base classes from the list of base classes."""
        return sorted(set(base_classes), key=lambda x: x.lower())

    @field_serializer("display_name")
    def process_display_name(self, display_name: str) -> str:
        """Sets the display name of the frontend node."""
        return display_name or self.name

    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        result = handler(self)
        if hasattr(self, "template") and hasattr(self.template, "to_dict"):
            result["template"] = self.template.to_dict()
        name = result.pop("name")

        # Migrate base classes to outputs
        if "output_types" in result and not result.get("outputs"):
            for base_class in result["output_types"]:
                output = Output(
                    display_name=base_class,
                    name=base_class.lower(),
                    types=[base_class],
                    selected=base_class,
                )
                result["outputs"].append(output.model_dump())

        return {name: result}

    @classmethod
    def from_dict(cls, data: dict) -> "FrontendNode":
        if "template" in data:
            data["template"] = Template.from_dict(data["template"])
        return cls(**data)

    # For backwards compatibility
    def to_dict(self, *, keep_name=True) -> dict:
        """Returns a dict representation of the frontend node."""
        dump = self.model_dump(by_alias=True, exclude_none=True)
        if not keep_name:
            return dump.pop(self.name)
        return dump

    def add_extra_fields(self) -> None:
        pass

    def add_extra_base_classes(self) -> None:
        pass

    def set_base_classes_from_outputs(self) -> None:
        self.base_classes = [output_type for output in self.outputs for output_type in output.types]

    def validate_component(self) -> None:
        self.validate_name_overlap()
        self.validate_attributes()

    def validate_name_overlap(self) -> None:
        # Check if any of the output names overlap with the any of the inputs
        output_names = [output.name for output in self.outputs]
        input_names = [input_.name for input_ in self.template.fields]
        overlap = set(output_names).intersection(input_names)
        if overlap:
            overlap_str = ", ".join(f"'{x}'" for x in overlap)
            msg = f"There should be no overlap between input and output names. Names {overlap_str} are duplicated."
            raise ValueError(msg)

    def validate_attributes(self) -> None:
        # None of inputs, outputs, _artifacts, _results, logs, status, vertex, graph, display_name, description,
        # documentation, icon should be present in outputs or input names
        output_names = [output.name for output in self.outputs]
        input_names = [input_.name for input_ in self.template.fields]
        attributes = [
            "inputs",
            "outputs",
            "_artifacts",
            "_results",
            "logs",
            "status",
            "vertex",
            "graph",
            "display_name",
            "description",
            "documentation",
            "icon",
        ]
        output_overlap = set(output_names).intersection(attributes)
        input_overlap = set(input_names).intersection(attributes)
        error_message = ""
        if output_overlap:
            output_overlap_str = ", ".join(f"'{x}'" for x in output_overlap)
            error_message += f"Output names {output_overlap_str} are reserved attributes.\n"
        if input_overlap:
            input_overlap_str = ", ".join(f"'{x}'" for x in input_overlap)
            error_message += f"Input names {input_overlap_str} are reserved attributes."

    def add_base_class(self, base_class: str | list[str]) -> None:
        """Adds a base class to the frontend node."""
        if isinstance(base_class, str):
            self.base_classes.append(base_class)
        elif isinstance(base_class, list):
            self.base_classes.extend(base_class)

    def add_output_type(self, output_type: str | list[str]) -> None:
        """Adds an output type to the frontend node."""
        if isinstance(output_type, str):
            self.output_types.append(output_type)
        elif isinstance(output_type, list):
            self.output_types.extend(output_type)

    @classmethod
    def from_inputs(cls, **kwargs):
        """Create a frontend node from inputs."""
        if "inputs" not in kwargs:
            msg = "Missing 'inputs' argument."
            raise ValueError(msg)
        if "_outputs_map" in kwargs:
            kwargs["outputs"] = kwargs.pop("_outputs_map")
        inputs = kwargs.pop("inputs")
        template = Template(type_name="Component", fields=inputs)
        kwargs["template"] = template
        return cls(**kwargs)

    def set_field_value_in_template(self, field_name, value) -> None:
        for idx, field in enumerate(self.template.fields):
            if field.name == field_name:
                new_field = field.model_copy()
                new_field.value = value
                self.template.fields[idx] = new_field
                break

    def set_field_load_from_db_in_template(self, field_name, value) -> None:
        for idx, field in enumerate(self.template.fields):
            if field.name == field_name and hasattr(field, "load_from_db"):
                new_field = field.model_copy()
                new_field.load_from_db = value
                self.template.fields[idx] = new_field
                break
