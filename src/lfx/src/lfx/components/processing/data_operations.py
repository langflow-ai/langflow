import ast
import json
from typing import TYPE_CHECKING, Any

from json_repair import repair_json

from lfx.custom import Component
from lfx.inputs import DictInput, DropdownInput, MessageTextInput, SortableListInput
from lfx.io import DataInput, MultilineInput, Output
from lfx.log.logger import logger
from lfx.schema import Data
from lfx.schema.dotdict import dotdict
from lfx.utils.component_utils import set_current_fields, set_field_display

if TYPE_CHECKING:
    from collections.abc import Callable

ACTION_CONFIG = {
    "Select Keys": {"is_list": False, "log_msg": "setting filter fields"},
    "Literal Eval": {"is_list": False, "log_msg": "setting evaluate fields"},
    "Combine": {"is_list": True, "log_msg": "setting combine fields"},
    "Append or Update": {"is_list": False, "log_msg": "setting Append or Update fields"},
    "Remove Keys": {"is_list": False, "log_msg": "setting remove keys fields"},
    "Rename Keys": {"is_list": False, "log_msg": "setting rename keys fields"},
    "Path Selection": {"is_list": False, "log_msg": "setting mapped key extractor fields"},
    "JQ Expression": {"is_list": False, "log_msg": "setting parse json fields"},
}


class DataOperationsComponent(Component):
    display_name = "JSON Operations"
    description = "Perform various operations on a JSON object."
    icon = "file-json"
    name = "DataOperations"
    legacy = True
    replacement = ["processing.Operations"]
    default_keys = ["operations", "data"]
    metadata = {
        "keywords": [
            "data",
            "json",
            "operations",
            "Append or Update",
            "remove keys",
            "rename keys",
            "select keys",
            "literal eval",
            "combine",
            "append",
            "update",
            "remove",
            "rename",
            "data operations",
            "json operations",
            "data manipulation",
            "data transformation",
            "data filtering",
            "data selection",
            "data combination",
            "Parse JSON",
            "JSON Query",
            "JQ Query",
        ],
    }
    actions_data = {
        "Select Keys": ["select_keys_input", "operations"],
        "Literal Eval": [],
        "Combine": [],
        "Append or Update": ["append_update_data", "operations"],
        "Remove Keys": ["remove_keys_input", "operations"],
        "Rename Keys": ["rename_keys_input", "operations"],
        "Path Selection": ["mapped_json_display", "selected_key", "operations"],
        "JQ Expression": ["query", "operations"],
    }

    # All operation-specific input fields (used to hide and reset when no operation selected).
    ALL_OPERATION_FIELDS = [
        "select_keys_input",
        "append_update_data",
        "remove_keys_input",
        "rename_keys_input",
        "mapped_json_display",
        "selected_key",
        "query",
    ]

    @staticmethod
    def extract_all_paths(obj, path=""):
        paths = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_path = f"{path}.{k}" if path else f".{k}"
                paths.append(new_path)
                paths.extend(DataOperationsComponent.extract_all_paths(v, new_path))
        elif isinstance(obj, list) and obj:
            new_path = f"{path}[0]"
            paths.append(new_path)
            paths.extend(DataOperationsComponent.extract_all_paths(obj[0], new_path))
        return paths

    @staticmethod
    def remove_keys_recursive(obj, keys_to_remove):
        if isinstance(obj, dict):
            return {
                k: DataOperationsComponent.remove_keys_recursive(v, keys_to_remove)
                for k, v in obj.items()
                if k not in keys_to_remove
            }
        if isinstance(obj, list):
            return [DataOperationsComponent.remove_keys_recursive(item, keys_to_remove) for item in obj]
        return obj

    @staticmethod
    def rename_keys_recursive(obj, rename_map):
        if isinstance(obj, dict):
            return {
                rename_map.get(k, k): DataOperationsComponent.rename_keys_recursive(v, rename_map)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [DataOperationsComponent.rename_keys_recursive(item, rename_map) for item in obj]
        return obj

    inputs = [
        DataInput(name="data", display_name="JSON", info="Data object to filter.", required=True, is_list=True),
        SortableListInput(
            name="operations",
            display_name="Operations",
            placeholder="Select Operation",
            info="List of operations to perform on the data.",
            options=[
                {"name": "Select Keys", "icon": "lasso-select"},
                {"name": "Literal Eval", "icon": "braces"},
                {"name": "Combine", "icon": "merge"},
                {"name": "Append or Update", "icon": "circle-plus"},
                {"name": "Remove Keys", "icon": "eraser"},
                {"name": "Rename Keys", "icon": "pencil-line"},
                {"name": "Path Selection", "icon": "mouse-pointer"},
                {"name": "JQ Expression", "icon": "terminal"},
            ],
            real_time_refresh=True,
            limit=1,
        ),
        # select keys inputs
        MessageTextInput(
            name="select_keys_input",
            display_name="Select Keys",
            info="List of keys to select from the data. Only top-level keys can be selected.",
            show=False,
            is_list=True,
            value=[],
        ),
        # update/ Append data inputs
        DictInput(
            name="append_update_data",
            display_name="Append or Update",
            info="Data to append or update the existing data with. Only top-level keys are checked.",
            show=False,
            value={"key": "value"},
            is_list=True,
        ),
        # remove keys inputs
        MessageTextInput(
            name="remove_keys_input",
            display_name="Remove Keys",
            info="List of keys to remove from the data.",
            show=False,
            is_list=True,
            value=[],
        ),
        # rename keys inputs
        DictInput(
            name="rename_keys_input",
            display_name="Rename Keys",
            info="List of keys to rename in the data.",
            show=False,
            is_list=True,
            value={"old_key": "new_key"},
        ),
        MultilineInput(
            name="mapped_json_display",
            display_name="JSON to Map",
            info="Paste or preview your JSON here to explore its structure and select a path for extraction.",
            required=False,
            refresh_button=True,
            real_time_refresh=True,
            placeholder="Add a JSON example.",
            show=False,
        ),
        DropdownInput(
            name="selected_key",
            display_name="Select Path",
            options=[],
            required=False,
            dynamic=True,
            show=False,
            value=None,
        ),
        MessageTextInput(
            name="query",
            display_name="JQ Expression",
            info="JSON Query to filter the data. Used by Parse JSON operation.",
            placeholder="e.g., .properties.id",
            show=False,
        ),
    ]

    # Default values for operation fields when clearing (match input definitions)
    OPERATION_FIELD_DEFAULTS: dict[str, Any] = {
        "select_keys_input": [],
        "append_update_data": {"key": "value"},
        "remove_keys_input": [],
        "rename_keys_input": {"old_key": "new_key"},
        "mapped_json_display": "",
        "selected_key": None,
        "query": "",
    }

    outputs = [
        Output(display_name="JSON", name="data_output", method="as_data"),
    ]

    # Helper methods for data operations
    def get_data_dict(self) -> dict:
        """Extract data dictionary from Data object."""
        data = self.data[0] if isinstance(self.data, list) and len(self.data) == 1 else self.data
        return data.model_dump()

    def json_query(self) -> Data:
        import json

        try:
            import jq
        except ImportError:
            msg = "jq is required for JQ Expression. Install with: pip install jq"
            raise ImportError(msg) from None

        if not self.query or not self.query.strip():
            msg = "JSON Query is required and cannot be blank."
            raise ValueError(msg)
        raw_data = self.get_data_dict()
        try:
            input_str = json.dumps(raw_data)
            repaired = repair_json(input_str)
            data_json = json.loads(repaired)
            jq_input = data_json["data"] if isinstance(data_json, dict) and "data" in data_json else data_json
            results = jq.compile(self.query).input(jq_input).all()
            if not results:
                msg = "No result from JSON query."
                raise ValueError(msg)
            result = results[0] if len(results) == 1 else results
            if result is None or result == "None":
                msg = "JSON query returned null/None. Check if the path exists in your data."
                raise ValueError(msg)
            if isinstance(result, dict):
                return Data(data=result)
            return Data(data={"result": result})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            logger.error(f"JSON Query failed: {e}")
            msg = f"JSON Query error: {e}"
            raise ValueError(msg) from e

    def get_normalized_data(self) -> dict:
        """Get normalized data dictionary, handling the 'data' key if present."""
        data_dict = self.get_data_dict()
        return data_dict.get("data", data_dict)

    def data_is_list(self) -> bool:
        """Check if data contains multiple items."""
        return isinstance(self.data, list) and len(self.data) > 1

    def validate_single_data(self, operation: str) -> None:
        """Validate that the operation is being performed on a single data object."""
        if self.data_is_list():
            msg = f"{operation} operation is not supported for multiple data objects."
            raise ValueError(msg)

    def operation_exception(self, operations: list[str]) -> None:
        """Raise exception for incompatible operations."""
        msg = f"{operations} operations are not supported in combination with each other."
        raise ValueError(msg)

    # Data transformation operations
    def select_keys(self, *, evaluate: bool | None = None) -> Data:
        """Select specific keys from the data dictionary."""
        self.validate_single_data("Select Keys")
        data_dict = self.get_normalized_data()
        filter_criteria: list[str] = self.select_keys_input

        # Filter the data
        if len(filter_criteria) == 1 and filter_criteria[0] == "data":
            filtered = data_dict["data"]
        else:
            if not all(key in data_dict for key in filter_criteria):
                msg = f"Select key not found in data. Available keys: {list(data_dict.keys())}"
                raise ValueError(msg)
            filtered = {key: value for key, value in data_dict.items() if key in filter_criteria}

        # Create a new Data object with the filtered data
        if evaluate:
            filtered = self.recursive_eval(filtered)

        # Return a new Data object with the filtered data directly in the data attribute
        return Data(data=filtered)

    def remove_keys(self) -> Data:
        """Remove specified keys from the data dictionary, recursively."""
        self.validate_single_data("Remove Keys")
        data_dict = self.get_normalized_data()
        remove_keys_input: list[str] = self.remove_keys_input

        filtered = DataOperationsComponent.remove_keys_recursive(data_dict, set(remove_keys_input))
        return Data(data=filtered)

    def rename_keys(self) -> Data:
        """Rename keys in the data dictionary, recursively."""
        self.validate_single_data("Rename Keys")
        data_dict = self.get_normalized_data()
        rename_keys_input: dict[str, str] = self.rename_keys_input

        renamed = DataOperationsComponent.rename_keys_recursive(data_dict, rename_keys_input)
        return Data(data=renamed)

    def recursive_eval(self, data: Any) -> Any:
        """Recursively evaluate string values in a dictionary or list.

        If the value is a string that can be evaluated, it will be evaluated.
        Otherwise, the original value is returned.
        """
        if isinstance(data, dict):
            return {k: self.recursive_eval(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.recursive_eval(item) for item in data]
        if isinstance(data, str):
            try:
                # Only attempt to evaluate strings that look like Python literals
                if (
                    data.strip().startswith(("{", "[", "(", "'", '"'))
                    or data.strip().lower() in ("true", "false", "none")
                    or data.strip().replace(".", "").isdigit()
                ):
                    return ast.literal_eval(data)
                # return data
            except (ValueError, SyntaxError, TypeError, MemoryError):
                # If evaluation fails for any reason, return the original string
                return data
            else:
                return data
        return data

    def evaluate_data(self) -> Data:
        """Evaluate string values in the data dictionary."""
        self.validate_single_data("Literal Eval")
        logger.info("evaluating data")
        return Data(**self.recursive_eval(self.get_data_dict()))

    def combine_data(self, *, evaluate: bool | None = None) -> Data:
        """Combine multiple data objects into one."""
        logger.info("combining data")
        if not self.data_is_list():
            return self.data[0] if self.data else Data(data={})

        if len(self.data) == 1:
            msg = "Combine operation requires multiple data inputs."
            raise ValueError(msg)

        data_dicts = [data.model_dump().get("data", data.model_dump()) for data in self.data]
        combined_data = {}

        for data_dict in data_dicts:
            for key, value in data_dict.items():
                if key not in combined_data:
                    combined_data[key] = value
                elif isinstance(combined_data[key], list):
                    if isinstance(value, list):
                        combined_data[key].extend(value)
                    else:
                        combined_data[key].append(value)
                else:
                    # If current value is not a list, convert it to list and add new value
                    combined_data[key] = (
                        [combined_data[key], value] if not isinstance(value, list) else [combined_data[key], *value]
                    )

        if evaluate:
            combined_data = self.recursive_eval(combined_data)

        return Data(**combined_data)

    def append_update(self) -> Data:
        """Append or Update with new key-value pairs."""
        self.validate_single_data("Append or Update")
        data_filtered = self.get_normalized_data()

        for key, value in self.append_update_data.items():
            data_filtered[key] = value

        return Data(**data_filtered)

    # Configuration and execution methods
    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "operations":
            build_config["operations"]["value"] = field_value
            # Mirror Text Operations: first hide all operation-specific fields and clear their values
            for field in self.ALL_OPERATION_FIELDS:
                if field in build_config:
                    build_config[field]["show"] = False
                    if field in self.OPERATION_FIELD_DEFAULTS:
                        build_config[field]["value"] = self.OPERATION_FIELD_DEFAULTS[field]

            selected_actions = [
                action["name"] for action in (field_value or []) if isinstance(action, dict) and "name" in action
            ]
            if len(selected_actions) == 1 and selected_actions[0] in ACTION_CONFIG:
                action = selected_actions[0]
                config = ACTION_CONFIG[action]
                build_config["data"]["is_list"] = config["is_list"]
                logger.info(config["log_msg"])
                return set_current_fields(
                    build_config=build_config,
                    action_fields=self.actions_data,
                    selected_action=action,
                    default_fields=["operations", "data"],
                    func=set_field_display,
                )
            return build_config

        if field_name == "mapped_json_display":
            try:
                parsed_json = json.loads(field_value)
                keys = DataOperationsComponent.extract_all_paths(parsed_json)
                build_config["selected_key"]["options"] = keys
                build_config["selected_key"]["show"] = True
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.error(f"Error parsing mapped JSON: {e}")
                build_config["selected_key"]["show"] = False

        return build_config

    def json_path(self) -> Data:
        try:
            import jq
        except ImportError:
            msg = "jq is required for Path Selection. Install with: pip install jq"
            raise ImportError(msg) from None

        try:
            if not self.data or not self.selected_key:
                msg = "Missing input data or selected key."
                raise ValueError(msg)
            input_payload = self.data[0].data if isinstance(self.data, list) else self.data.data
            compiled = jq.compile(self.selected_key)
            result = compiled.input(input_payload).first()
            if isinstance(result, dict):
                return Data(data=result)
            return Data(data={"result": result})
        except (ValueError, TypeError, KeyError) as e:
            self.status = f"Error: {e!s}"
            self.log(self.status)
            return Data(data={"error": str(e)})

    def as_data(self) -> Data:
        if not hasattr(self, "operations") or not self.operations:
            return Data(data={})

        selected_actions = [action["name"] for action in self.operations]
        logger.info(f"selected_actions: {selected_actions}")
        if len(selected_actions) != 1:
            return Data(data={})

        action_map: dict[str, Callable[[], Data]] = {
            "Select Keys": self.select_keys,
            "Literal Eval": self.evaluate_data,
            "Combine": self.combine_data,
            "Append or Update": self.append_update,
            "Remove Keys": self.remove_keys,
            "Rename Keys": self.rename_keys,
            "Path Selection": self.json_path,
            "JQ Expression": self.json_query,
        }
        action_name = selected_actions[0]
        handler: Callable[[], Data] | None = action_map.get(action_name)
        if handler is None:
            # Fail fast instead of silently returning empty data. Persisted flows
            # may still reference a removed operation (e.g. "Filter Values").
            msg = (
                f"The '{action_name}' operation is no longer supported by the JSON Operations component. "
                "Update this flow to use the Operations component."
            )
            raise ValueError(msg)
        try:
            return handler()
        except Exception as e:
            logger.error(f"Error executing {action_name}: {e!s}")
            raise
