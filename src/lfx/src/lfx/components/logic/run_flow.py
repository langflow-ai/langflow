from typing import Any

from lfx.base.tools.run_flow import RunFlowBaseComponent
from lfx.helpers import run_flow
from lfx.log.logger import logger
from lfx.schema.dotdict import dotdict


class RunFlowComponent(RunFlowBaseComponent):
    display_name = "Run Flow"
    description = (
        "Creates a tool component from a Flow that takes all its inputs and runs it. "
        " \n **Select a Flow to use the tool mode**"
    )
    documentation: str = "https://docs.langflow.org/components-logic#run-flow"
    beta = True
    name = "RunFlow"
    icon = "Workflow"

    inputs = RunFlowBaseComponent.get_base_inputs()
    outputs = RunFlowBaseComponent.get_base_outputs()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.flow_output_types = []  # Cache for output types from selected flow

    def update_outputs(self, frontend_node: dict, field_name: str, field_value) -> dict:
        """Dynamically update outputs based on the selected flow."""
        if field_name != "flow_name_selected":
            return frontend_node
            
        from lfx.template.field.base import Output
            
        if not field_value:
            # No flow selected - no outputs
            frontend_node["outputs"] = []
            return frontend_node
            
        # Flow selected - create dynamic outputs based on the flow's actual outputs
        frontend_node["outputs"] = []
        
        if hasattr(self, 'flow_output_types') and self.flow_output_types:
            # Use the actual output types from the selected flow
            for output_info in self.flow_output_types:
                frontend_node["outputs"].append(
                    Output(
                        display_name=output_info["display_name"],
                        name=output_info["name"],
                        method="flow_output",
                        types=output_info["types"],
                    )
                )
        else:
            # Fallback: create a generic output if no type info available
            frontend_node["outputs"] = [
                Output(
                    display_name="Flow Output",
                    name="flow_output", 
                    method="flow_output",
                    # No types - will be inferred at runtime
                )
            ]
        
        return frontend_node

    def extract_output_types_from_graph(self, graph) -> list:
        """Extract output type information from the flow's graph."""
        output_info = []
        
        try:
            # Find all output vertices (components that are outputs)
            output_vertices = [v for v in graph.vertices if v.is_output]
            
            # Check if we have multiple outputs to determine display name strategy
            has_multiple_outputs = len(output_vertices) > 1
            
            for vertex in output_vertices:
                # Get outputs from the vertex
                vertex_outputs = vertex.outputs if hasattr(vertex, 'outputs') else []
                
                if not vertex_outputs and vertex.data.get("node", {}).get("outputs"):
                    vertex_outputs = vertex.data["node"]["outputs"]
                
                for output in vertex_outputs:
                    # Choose display name based on number of outputs
                    if has_multiple_outputs:
                        # Multiple outputs: use component name + ID suffix for clarity
                        # Extract just the ID suffix (e.g., "msvr6" from "ChatOutput-msvr6")
                        id_suffix = vertex.id.split('-')[-1] if '-' in vertex.id else vertex.id
                        display_name = f"{vertex.display_name} - {id_suffix}"
                    else:
                        # Single output: use just the component name (e.g., "Chat Output")
                        display_name = vertex.display_name
                    
                    output_name = output.get("name", "output")
                    # Always use component ID in technical name to ensure uniqueness
                    name = f"{vertex.id}_{output_name}"
                    
                    # Determine output type based on component type
                    base_classes = vertex.data.get("node", {}).get("base_classes", [])
                    if not base_classes:
                        # Fallback: infer from vertex ID or display name
                        vertex_id = vertex.id or ""
                        if "ChatOutput" in vertex_id:
                            base_classes = ["Message"]
                        elif "TextOutput" in vertex_id:
                            base_classes = ["Message"]
                        # Future output types - add here when they exist
                        else:
                            # Default fallback
                            base_classes = ["Message"]
                    
                    output_info.append({
                        "display_name": display_name,
                        "name": name,
                        "types": base_classes
                    })
                    
        except Exception as e:
            logger.error(f"Error extracting output types from graph: {e}")
            
        return output_info

    async def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "flow_name_selected":
            build_config["flow_name_selected"]["options"] = await self.get_flow_names()
            missing_keys = [key for key in self.default_keys if key not in build_config]
            if missing_keys:
                msg = f"Missing required keys in build_config: {missing_keys}"
                raise ValueError(msg)
            if field_value is not None:
                try:
                    graph = await self.get_graph(field_value)
                    build_config = self.update_build_config_from_graph(build_config, graph)
                    
                    # Extract output types from the flow for dynamic output creation
                    self.flow_output_types = self.extract_output_types_from_graph(graph)
                except Exception as e:
                    msg = f"Error building graph for flow {field_value}"
                    await logger.aexception(msg)
                    self.flow_output_types = []  # Reset on error
                    raise RuntimeError(msg) from e
        return build_config

    async def run_flow_with_tweaks(self):
        tweaks: dict = {}

        flow_name_selected = self._attributes.get("flow_name_selected")
        parsed_flow_tweak_data = self._attributes.get("flow_tweak_data", {})
        if not isinstance(parsed_flow_tweak_data, dict):
            parsed_flow_tweak_data = parsed_flow_tweak_data.dict()

        if parsed_flow_tweak_data != {}:
            for field in parsed_flow_tweak_data:
                if "~" in field:
                    [node, name] = field.split("~")
                    if node not in tweaks:
                        tweaks[node] = {}
                    tweaks[node][name] = parsed_flow_tweak_data[field]
        else:
            for field in self._attributes:
                if field not in self.default_keys and "~" in field:
                    [node, name] = field.split("~")
                    if node not in tweaks:
                        tweaks[node] = {}
                    tweaks[node][name] = self._attributes[field]

        return await run_flow(
            inputs=None,
            output_type="all",
            flow_id=None,
            flow_name=flow_name_selected,
            tweaks=tweaks,
            user_id=str(self.user_id),
            session_id=self.graph.session_id or self.session_id,
        )
