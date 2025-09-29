import sys
from typing import Any

from langflow.custom import Component
from langflow.io import BoolInput, DropdownInput, Output, StrInput
from langflow.schema import Data


class UniversalOutputSelectorComponent(Component):
    display_name = "Universal Output Selector"
    description = "Selects and retrieves the value from any output of any component in the flow"
    icon = "selector"

    inputs = [
        DropdownInput(
            name="selected_output",
            display_name="Select Output",
            info="Choose any output from any component in the flow",
            options=[
                "Chat Input → Chat Message",
                "Prompt → Prompt",
                "Language Model → Model Response",
                "Chat Output → Output Message"
            ],  # Static test options
            real_time_refresh=True,  # Enable real-time refresh
            value=None,
        ),
        BoolInput(
            name="include_self",
            display_name="Include Self",
            info="Whether to include outputs from this component itself",
            value=False,
            advanced=True,
        ),
        StrInput(
            name="filter_types",
            display_name="Filter Types",
            info="Comma-separated list of output types to filter (e.g., 'Message,Data'). Leave empty for all types.",
            value="",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Selected Value", name="selected_value", method="get_selected_value"),
        Output(display_name="Output Info", name="output_info", method="get_output_info"),
        Output(display_name="Available Outputs", name="available_outputs", method="get_available_outputs"),
    ]

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update the dropdown options when the component is refreshed"""
        # Force print to stderr to ensure it shows up
        print(f"DEBUG: ASYNC update_build_config called with field_name={field_name}, field_value={field_value}", file=sys.stderr)
        sys.stderr.flush()

        try:
            # Always update dropdown options regardless of field_name
            print("DEBUG: Updating dropdown options for selected_output...", file=sys.stderr)

            # Get available outputs from the flow
            available_outputs = self._discover_available_outputs()

            print(f"DEBUG: Found {len(available_outputs)} outputs: {available_outputs}", file=sys.stderr)

            # Create simple list of options for dropdown
            options = []
            for component_id, output_name, output_types in available_outputs:
                # Use display name if available
                display_name = self._get_component_display_name(component_id)
                option_text = f"{display_name} → {output_name}"
                options.append(option_text)

            # Update the dropdown options
            build_config["selected_output"]["options"] = options

            print(f"DEBUG: Options set to: {build_config['selected_output']['options']}", file=sys.stderr)
            sys.stderr.flush()

        except Exception as e:
            print(f"ERROR in update_build_config: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()

        return build_config

    def _discover_available_outputs(self) -> list[tuple[str, str, list[str]]]:
        """Discover all available outputs in the flow"""
        available_outputs = []

        if not hasattr(self, "graph") or self.graph is None:
            print("DEBUG: No graph available", file=sys.stderr)
            return available_outputs

        include_self = getattr(self, "include_self", False)
        filter_types = getattr(self, "filter_types", "")
        type_filters = [t.strip() for t in filter_types.split(",") if t.strip()] if filter_types else []

        print(f"DEBUG: Starting discovery. Graph has vertex_map: {hasattr(self.graph, 'vertex_map')}, _vertices: {hasattr(self.graph, '_vertices')}, raw_graph_data: {hasattr(self.graph, 'raw_graph_data')}", file=sys.stderr)

        # Primary approach: vertex_map (fully initialized components)
        if hasattr(self.graph, "vertex_map") and self.graph.vertex_map:
            print(f"DEBUG: Using vertex_map with {len(self.graph.vertex_map)} vertices", file=sys.stderr)
            for vertex_id, vertex in self.graph.vertex_map.items():
                self._extract_outputs_from_vertex(vertex, vertex_id, available_outputs, include_self, type_filters)

        # Secondary approach: raw_graph_data (original flow definition)
        elif hasattr(self.graph, "raw_graph_data") and self.graph.raw_graph_data and self.graph.raw_graph_data.get("nodes"):
            print(f"DEBUG: Using raw_graph_data with {len(self.graph.raw_graph_data['nodes'])} nodes", file=sys.stderr)
            for node_data in self.graph.raw_graph_data["nodes"]:
                self._extract_outputs_from_node_data(node_data, available_outputs, include_self, type_filters)

        # Tertiary approach: _vertices (raw canvas data)
        elif hasattr(self.graph, "_vertices") and self.graph._vertices:
            print(f"DEBUG: Using _vertices with {len(self.graph._vertices)} items", file=sys.stderr)
            for node_data in self.graph._vertices:
                self._extract_outputs_from_node_data(node_data, available_outputs, include_self, type_filters)

        else:
            print("DEBUG: No graph data source available", file=sys.stderr)

        print(f"DEBUG: Discovered {len(available_outputs)} outputs: {available_outputs}", file=sys.stderr)

        # Sort by component display name and output name for better UX
        available_outputs.sort(key=lambda x: (self._get_component_display_name(x[0]), x[1]))
        return available_outputs

    def _extract_outputs_from_vertex(self, vertex, vertex_id: str, available_outputs: list, include_self: bool, type_filters: list):
        """Extract outputs from a vertex object"""
        # Skip self unless explicitly included
        if not include_self and hasattr(self, "_id") and vertex_id == self._id:
            return

        # Get outputs for this vertex
        vertex_outputs = getattr(vertex, "outputs", [])
        if not vertex_outputs:
            # Try alternative attributes
            vertex_outputs = getattr(vertex, "output", [])
            if not vertex_outputs and hasattr(vertex, "data"):
                node_data = getattr(vertex, "data", {})
                if isinstance(node_data, dict):
                    vertex_outputs = node_data.get("node", {}).get("outputs", [])

        if not vertex_outputs:
            return

        for output in vertex_outputs:
            if isinstance(output, dict):
                output_name = output.get("name", "")
                output_types = output.get("types", [])
            else:
                output_name = getattr(output, "name", "")
                output_types = getattr(output, "types", [])

            if not output_name:
                continue

            # Apply type filtering if specified
            if type_filters:
                if not any(filter_type in output_types for filter_type in type_filters):
                    continue

            available_outputs.append((vertex_id, output_name, output_types))

    def _extract_outputs_from_node_data(self, node_data: dict, available_outputs: list, include_self: bool, type_filters: list):
        """Extract outputs from raw node data (canvas components before graph initialization)"""
        vertex_id = node_data.get("id", "")
        if not vertex_id:
            return

        # Skip self unless explicitly included
        if not include_self and hasattr(self, "_id") and vertex_id == self._id:
            return

        # Skip note nodes
        if node_data.get("type") == "NoteNode":
            return

        # Extract node information
        data = node_data.get("data", {})
        node = data.get("node", {})

        # Get outputs from the node template or data
        outputs = node.get("outputs", [])

        # If no outputs defined, try to infer from component type
        if not outputs:
            node_type = data.get("type", "")
            base_classes = node.get("base_classes", [])

            # Common output patterns for different component types
            if "Input" in node_type or any("Input" in cls for cls in base_classes):
                outputs = [
                    {"name": "text", "types": ["str"]},
                    {"name": "message", "types": ["Message"]}
                ]
            elif "LLM" in node_type or any("LLM" in cls for cls in base_classes):
                outputs = [
                    {"name": "text", "types": ["str"]},
                    {"name": "response", "types": ["Message"]}
                ]
            elif "Retriever" in node_type or any("Retriever" in cls for cls in base_classes):
                outputs = [
                    {"name": "documents", "types": ["List[Document]"]}
                ]
            elif "Tool" in node_type or any("Tool" in cls for cls in base_classes):
                outputs = [
                    {"name": "output", "types": ["str"]},
                    {"name": "result", "types": ["Any"]}
                ]
            else:
                # Generic fallback
                outputs = [
                    {"name": "output", "types": ["Any"]}
                ]

        # Process each output
        for output in outputs:
            if isinstance(output, dict):
                output_name = output.get("name", "")
                output_types = output.get("types", [])
            else:
                # Handle string or other formats
                output_name = str(output)
                output_types = ["Any"]

            if not output_name:
                continue

            # Apply type filtering if specified
            if type_filters:
                if not any(filter_type in output_types for filter_type in type_filters):
                    continue

            available_outputs.append((vertex_id, output_name, output_types))

    def _get_component_display_name(self, vertex_id: str) -> str:
        """Get the display name for a component"""
        if not hasattr(self, "graph") or self.graph is None:
            return vertex_id.split("-")[0]

        # First try to get from raw node data (_vertices)
        if hasattr(self.graph, "_vertices") and self.graph._vertices:
            for node_data in self.graph._vertices:
                if node_data.get("id") == vertex_id:
                    data = node_data.get("data", {})
                    display_name = data.get("display_name") or data.get("type", "")
                    return display_name if display_name else vertex_id.split("-")[0]

        # Fallback to vertex_map (after graph initialization)
        try:
            vertex = self.graph.get_vertex(vertex_id)
            return getattr(vertex, "display_name", vertex_id.split("-")[0])
        except (ValueError, AttributeError):
            return vertex_id.split("-")[0]

    def _parse_selection(self, selection: str) -> tuple[str, str] | None:
        """Parse the selected output string into component_id and output_name"""
        if not selection or "→" not in selection:
            return None

        try:
            display_name, output_name = selection.split("→", 1)
            display_name = display_name.strip()
            output_name = output_name.strip()

            # Find the actual component_id that matches this display name
            if hasattr(self, "graph") and self.graph:
                # Check _vertices first (raw canvas data)
                if hasattr(self.graph, "_vertices"):
                    for node_data in self.graph._vertices:
                        node_display = node_data.get("data", {}).get("display_name") or node_data.get("data", {}).get("type", "")
                        if node_display == display_name:
                            return node_data.get("id"), output_name

                # Check vertex_map (processed components)
                if hasattr(self.graph, "vertex_map"):
                    for vertex_id, vertex in self.graph.vertex_map.items():
                        vertex_display = getattr(vertex, "display_name", vertex_id.split("-")[0])
                        if vertex_display == display_name:
                            return vertex_id, output_name

            # Fallback: assume display_name is the component_id
            return display_name, output_name

        except ValueError:
            return None

    def get_selected_value(self) -> Any:
        """Get the actual value from the selected output"""
        if not self.selected_output:
            return Data(data={"error": "No output selected"})

        parsed = self._parse_selection(self.selected_output)
        if not parsed:
            return Data(data={"error": f"Invalid selection format: {self.selected_output}"})

        component_id, output_name = parsed

        if not hasattr(self, "graph") or self.graph is None:
            return Data(data={"error": "Graph not available"})

        try:
            # Get the target vertex
            target_vertex = self.graph.get_vertex(component_id)

            # Check if the vertex has been built and has results
            if not hasattr(target_vertex, "results") or not target_vertex.results:
                return Data(data={
                    "warning": f"Component {self._get_component_display_name(component_id)} has not been executed yet",
                    "component_id": component_id,
                    "output_name": output_name
                })

            # Get the specific output value
            if output_name in target_vertex.results:
                result = target_vertex.results[output_name]
                return result if result is not None else Data(data={"value": None})
            available_outputs = list(target_vertex.results.keys())
            return Data(data={
                "error": f"Output '{output_name}' not found in component results",
                "available_outputs": available_outputs
            })

        except ValueError:
            return Data(data={"error": f"Component not found: {component_id}"})
        except Exception as e:
            return Data(data={"error": f"Error retrieving value: {e!s}"})

    def get_output_info(self) -> Data:
        """Get information about the selected output"""
        if not self.selected_output:
            return Data(data={"info": "No output selected"})

        parsed = self._parse_selection(self.selected_output)
        if not parsed:
            return Data(data={"error": f"Invalid selection format: {self.selected_output}"})

        component_id, output_name = parsed

        if not hasattr(self, "graph") or self.graph is None:
            return Data(data={"error": "Graph not available"})

        try:
            target_vertex = self.graph.get_vertex(component_id)
            component_display = self._get_component_display_name(component_id)

            # Find the output definition
            output_info = None
            vertex_outputs = getattr(target_vertex, "outputs", [])

            for output in vertex_outputs:
                if isinstance(output, dict):
                    if output.get("name") == output_name:
                        output_info = output
                        break
                elif getattr(output, "name", "") == output_name:
                    output_info = {
                        "name": output.name,
                        "types": getattr(output, "types", []),
                        "method": getattr(output, "method", ""),
                        "display_name": getattr(output, "display_name", output.name)
                    }
                    break

            info_data = {
                "component_id": component_id,
                "component_display_name": component_display,
                "output_name": output_name,
                "output_info": output_info,
                "has_been_executed": hasattr(target_vertex, "results") and bool(target_vertex.results),
                "available_results": list(target_vertex.results.keys()) if hasattr(target_vertex, "results") and target_vertex.results else []
            }

            return Data(data=info_data)

        except ValueError:
            return Data(data={"error": f"Component not found: {component_id}"})
        except Exception as e:
            return Data(data={"error": f"Error getting info: {e!s}"})

    def get_available_outputs(self) -> Data:
        """Get a list of all available outputs in the flow"""
        available_outputs = self._discover_available_outputs()

        outputs_data = []
        for component_id, output_name, output_types in available_outputs:
            component_display = self._get_component_display_name(component_id)
            outputs_data.append({
                "component_id": component_id,
                "component_display_name": component_display,
                "output_name": output_name,
                "output_types": output_types,
                "selector_value": f"{component_id}::{output_name}"
            })

        return Data(data={
            "total_outputs": len(outputs_data),
            "outputs": outputs_data
        })
