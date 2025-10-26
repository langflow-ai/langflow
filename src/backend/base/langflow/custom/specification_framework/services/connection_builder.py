"""
Connection Builder Service

Professional service for building Langflow connections between workflow components
with automatic pattern detection and UI-compatible edge generation.
"""

import logging
import uuid
import json
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime

from ..models.processing_context import ProcessingContext
from ..models.error_models import (
    ErrorHandler, ErrorResult, ErrorCategory, ErrorSeverity, CommonErrorIds
)

logger = logging.getLogger(__name__)


class ConnectionBuilder:
    """
    Professional service for building workflow connections.

    This service replaces the poorly named 'edge_generator' with a comprehensive
    connection building system that creates UI-compatible Langflow edges.
    """

    def __init__(self):
        """Initialize the connection builder."""
        self._service_name = "ConnectionBuilder"
        self.error_handler = ErrorHandler(self._service_name)
        self.uuid_retry_attempts = 3
        self.json_formatting_timeout = 5.0

    async def build_connections(self,
                              components: Dict[str, Any],
                              component_mappings: Dict[str, Dict[str, Any]],
                              context: ProcessingContext) -> Union[List[Dict[str, Any]], ErrorResult]:
        """
        Build all connections for a workflow.

        Args:
            components: Component specifications
            component_mappings: Component discovery results
            context: Processing context

        Returns:
            List of Langflow-compatible edge structures or ErrorResult
        """
        start_time = datetime.utcnow()
        connections = []

        try:
            # Validate inputs
            validation_result = self._validate_build_inputs(components, component_mappings, context)
            if not validation_result.success:
                return validation_result

            # Phase 1: Build explicit connections from provides declarations
            explicit_result = await self._build_explicit_connections(
                components, component_mappings, context
            )
            if isinstance(explicit_result, ErrorResult):
                return explicit_result
            explicit_connections = explicit_result
            connections.extend(explicit_connections)

            # Phase 2: Build intelligent implicit connections
            implicit_result = await self._build_implicit_connections(
                components, component_mappings, context, explicit_connections
            )
            if isinstance(implicit_result, ErrorResult):
                return implicit_result
            implicit_connections = implicit_result
            connections.extend(implicit_connections)

            # Phase 3: Optimize and validate connections
            optimization_result = self._optimize_connections(connections, context)
            if isinstance(optimization_result, ErrorResult):
                return optimization_result
            optimized_connections = optimization_result

            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Built {len(optimized_connections)} connections "
                       f"({len(explicit_connections)} explicit, {len(implicit_connections)} implicit) "
                       f"in {execution_time:.3f}s")

            return optimized_connections

        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="build_connections",
                exception=e,
                error_id="connection_build_failed",
                category=ErrorCategory.CONNECTION,
                severity=ErrorSeverity.HIGH,
                retry_possible=True
            )
            return ErrorResult.error_result([error])

    async def _build_explicit_connections(self,
                                        components: Dict[str, Any],
                                        component_mappings: Dict[str, Dict[str, Any]],
                                        context: ProcessingContext) -> List[Dict[str, Any]]:
        """Build connections from explicit provides declarations."""
        connections = []

        # Normalize components format
        component_items = self._normalize_component_format(components)

        for comp_id, comp_data in component_items:
            provides = comp_data.get("provides", [])
            if not provides:
                continue

            source_mapping = component_mappings.get(comp_id)
            if not source_mapping:
                logger.warning(f"No mapping found for source component {comp_id}")
                continue

            for provide in provides:
                if not isinstance(provide, dict):
                    logger.warning(f"Invalid provide declaration in {comp_id}: {provide}")
                    continue

                target_comp_id = provide.get("in")
                use_as = provide.get("useAs", "input")

                if not target_comp_id:
                    logger.warning(f"Missing 'in' field in provide declaration: {provide}")
                    continue

                target_mapping = component_mappings.get(target_comp_id)
                if not target_mapping:
                    logger.warning(f"No mapping found for target component {target_comp_id}")
                    continue

                # Build connection
                connection = self._create_connection(
                    source_comp_id=comp_id,
                    target_comp_id=target_comp_id,
                    source_mapping=source_mapping,
                    target_mapping=target_mapping,
                    use_as=use_as,
                    is_explicit=True
                )

                if connection:
                    connections.append(connection)
                    logger.debug(f"Built explicit connection: {comp_id} -> {target_comp_id} (useAs: {use_as})")

        return connections

    async def _build_implicit_connections(self,
                                        components: Dict[str, Any],
                                        component_mappings: Dict[str, Dict[str, Any]],
                                        context: ProcessingContext,
                                        explicit_connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build intelligent implicit connections using workflow patterns."""
        implicit_connections = []

        # Get existing connection pairs
        connected_pairs = set()
        for conn in explicit_connections:
            source_id = self._extract_component_id_from_node(conn.get("source", ""))
            target_id = self._extract_component_id_from_node(conn.get("target", ""))
            connected_pairs.add((source_id, target_id))

        # Pattern 1: Input -> Agent -> Output chain
        await self._build_input_agent_output_chain(
            component_mappings, connected_pairs, implicit_connections
        )

        # Pattern 2: Tool -> Agent connections
        await self._build_tool_agent_connections(
            components, component_mappings, connected_pairs, implicit_connections
        )

        # Pattern 3: Healthcare workflow patterns
        await self._build_healthcare_patterns(
            components, component_mappings, connected_pairs, implicit_connections
        )

        return implicit_connections

    async def _build_input_agent_output_chain(self,
                                            component_mappings: Dict[str, Dict[str, Any]],
                                            connected_pairs: set,
                                            implicit_connections: List[Dict[str, Any]]):
        """Build Input -> Agent -> Output connection pattern."""
        # Find components by type
        input_components = self._find_components_by_type(component_mappings, ["genesis:chat_input"])
        agent_components = self._find_components_by_type(component_mappings, ["genesis:agent"])
        output_components = self._find_components_by_type(component_mappings, ["genesis:chat_output"])

        # Connect inputs to agents
        for input_comp_id, input_mapping in input_components:
            for agent_comp_id, agent_mapping in agent_components:
                if (input_comp_id, agent_comp_id) not in connected_pairs:
                    connection = self._create_connection(
                        source_comp_id=input_comp_id,
                        target_comp_id=agent_comp_id,
                        source_mapping=input_mapping,
                        target_mapping=agent_mapping,
                        use_as="input",
                        is_explicit=False
                    )
                    if connection:
                        implicit_connections.append(connection)
                        connected_pairs.add((input_comp_id, agent_comp_id))
                        logger.debug(f"Built implicit connection: {input_comp_id} -> {agent_comp_id} (input chain)")

        # Connect agents to outputs
        for agent_comp_id, agent_mapping in agent_components:
            for output_comp_id, output_mapping in output_components:
                if (agent_comp_id, output_comp_id) not in connected_pairs:
                    connection = self._create_connection(
                        source_comp_id=agent_comp_id,
                        target_comp_id=output_comp_id,
                        source_mapping=agent_mapping,
                        target_mapping=output_mapping,
                        use_as="response",
                        is_explicit=False
                    )
                    if connection:
                        implicit_connections.append(connection)
                        connected_pairs.add((agent_comp_id, output_comp_id))
                        logger.debug(f"Built implicit connection: {agent_comp_id} -> {output_comp_id} (output chain)")

    async def _build_tool_agent_connections(self,
                                          components: Dict[str, Any],
                                          component_mappings: Dict[str, Dict[str, Any]],
                                          connected_pairs: set,
                                          implicit_connections: List[Dict[str, Any]]):
        """Build Tool -> Agent connection patterns."""
        # Find tool and agent components
        tool_components = self._find_tool_components(components, component_mappings)
        agent_components = self._find_components_by_type(component_mappings, ["genesis:agent"])

        for tool_comp_id, tool_mapping in tool_components:
            for agent_comp_id, agent_mapping in agent_components:
                if (tool_comp_id, agent_comp_id) not in connected_pairs:
                    # Check if this tool should connect to this agent
                    if self._should_connect_tool_to_agent(tool_comp_id, agent_comp_id, components):
                        connection = self._create_connection(
                            source_comp_id=tool_comp_id,
                            target_comp_id=agent_comp_id,
                            source_mapping=tool_mapping,
                            target_mapping=agent_mapping,
                            use_as="tools",
                            is_explicit=False
                        )
                        if connection:
                            implicit_connections.append(connection)
                            connected_pairs.add((tool_comp_id, agent_comp_id))
                            logger.debug(f"Built implicit tool connection: {tool_comp_id} -> {agent_comp_id}")

    async def _build_healthcare_patterns(self,
                                        components: Dict[str, Any],
                                        component_mappings: Dict[str, Dict[str, Any]],
                                        connected_pairs: set,
                                        implicit_connections: List[Dict[str, Any]]):
        """Build healthcare-specific connection patterns."""
        # Find healthcare components
        ehr_components = self._find_components_by_type(component_mappings, ["genesis:ehr_connector"])
        claims_components = self._find_components_by_type(component_mappings, ["genesis:claims_connector"])
        agent_components = self._find_components_by_type(component_mappings, ["genesis:agent"])

        # Build EHR -> Agent -> Claims workflow patterns
        if ehr_components and claims_components and agent_components:
            ehr_comp_id, ehr_mapping = ehr_components[0]
            agent_comp_id, agent_mapping = agent_components[0]
            claims_comp_id, claims_mapping = claims_components[0]

            # EHR -> Agent
            if (ehr_comp_id, agent_comp_id) not in connected_pairs:
                connection = self._create_connection(
                    source_comp_id=ehr_comp_id,
                    target_comp_id=agent_comp_id,
                    source_mapping=ehr_mapping,
                    target_mapping=agent_mapping,
                    use_as="tools",
                    is_explicit=False
                )
                if connection:
                    implicit_connections.append(connection)
                    connected_pairs.add((ehr_comp_id, agent_comp_id))

            # Claims -> Agent
            if (claims_comp_id, agent_comp_id) not in connected_pairs:
                connection = self._create_connection(
                    source_comp_id=claims_comp_id,
                    target_comp_id=agent_comp_id,
                    source_mapping=claims_mapping,
                    target_mapping=agent_mapping,
                    use_as="tools",
                    is_explicit=False
                )
                if connection:
                    implicit_connections.append(connection)
                    connected_pairs.add((claims_comp_id, agent_comp_id))

    def _create_connection(self,
                          source_comp_id: str,
                          target_comp_id: str,
                          source_mapping: Dict[str, Any],
                          target_mapping: Dict[str, Any],
                          use_as: str,
                          is_explicit: bool) -> Union[Dict[str, Any], None, ErrorResult]:
        """Create a single Langflow connection with UI-compatible format."""
        try:
            # Generate unique node IDs for components with retry logic
            source_node_id = self._generate_uuid_with_retry("source_node", source_comp_id)
            if isinstance(source_node_id, ErrorResult):
                return source_node_id

            target_node_id = self._generate_uuid_with_retry("target_node", target_comp_id)
            if isinstance(target_node_id, ErrorResult):
                return target_node_id

            # Get component types with validation
            source_type = self._validate_component_type(source_mapping, source_comp_id)
            if isinstance(source_type, ErrorResult):
                return source_type

            target_type = self._validate_component_type(target_mapping, target_comp_id)
            if isinstance(target_type, ErrorResult):
                return target_type

            # Create handle data structures with error handling
            source_handle_result = self._create_source_handle_data_safe(source_type, source_node_id, use_as)
            if isinstance(source_handle_result, ErrorResult):
                return source_handle_result
            source_handle_data = source_handle_result

            target_handle_result = self._create_target_handle_data_safe(target_type, target_node_id, use_as)
            if isinstance(target_handle_result, ErrorResult):
                return target_handle_result
            target_handle_data = target_handle_result

            # Format handles as UI-compatible strings with error handling
            source_handle_str_result = self._format_handle_string_safe(source_handle_data)
            if isinstance(source_handle_str_result, ErrorResult):
                return source_handle_str_result
            source_handle_str = source_handle_str_result

            target_handle_str_result = self._format_handle_string_safe(target_handle_data)
            if isinstance(target_handle_str_result, ErrorResult):
                return target_handle_str_result
            target_handle_str = target_handle_str_result

            # Create edge ID in UI format
            edge_id = f"xy-edge__{source_node_id}{{{source_handle_str}}}-{target_node_id}{{{target_handle_str}}}"

            # Create UI-compatible connection structure
            connection = {
                "id": edge_id,
                "source": source_node_id,
                "target": target_node_id,
                "sourceHandle": source_handle_str,
                "targetHandle": target_handle_str,
                "selected": False,
                "className": "",
                "data": {
                    "sourceHandle": source_handle_data,
                    "targetHandle": target_handle_data
                }
            }

            return connection

        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="create_connection",
                exception=e,
                error_id=CommonErrorIds.CONNECTION_HANDLE_CREATION_FAILED,
                category=ErrorCategory.CONNECTION,
                severity=ErrorSeverity.HIGH,
                component_id=f"{source_comp_id}->{target_comp_id}",
                suggested_fix="Check component mappings and ensure types are valid",
                retry_possible=True
            )
            return ErrorResult.error_result([error])

    def _create_source_handle_data(self, component_type: str, node_id: str, use_as: str) -> Dict[str, Any]:
        """Create source handle data compatible with Langflow UI."""
        if "chat_input" in component_type:
            return {
                "dataType": "ChatInput",
                "id": node_id,
                "name": "message",
                "output_types": ["Message"]
            }
        elif "agent" in component_type:
            return {
                "dataType": "Agent",
                "id": node_id,
                "name": "response",  # Fixed: use "response" not "text_output"
                "output_types": ["Message"]
            }
        elif "chat_output" in component_type:
            return {
                "dataType": "ChatOutput",
                "id": node_id,
                "name": "message",
                "output_types": ["Message"]
            }
        else:
            # Default for other component types
            return {
                "dataType": component_type.replace("genesis:", "").title(),
                "id": node_id,
                "name": "output",
                "output_types": ["Data"]
            }

    def _create_target_handle_data(self, component_type: str, node_id: str, use_as: str) -> Dict[str, Any]:
        """Create target handle data compatible with Langflow UI."""
        if "chat_output" in component_type:
            return {
                "fieldName": "input_value",
                "id": node_id,
                "inputTypes": ["Data", "DataFrame", "Message"],
                "type": "other"  # Fixed: use "other" not "str"
            }
        elif "agent" in component_type:
            if use_as == "tools":
                return {
                    "fieldName": "tools",
                    "id": node_id,
                    "inputTypes": ["Tool"],
                    "type": "list"
                }
            else:
                return {
                    "fieldName": "input_value",
                    "id": node_id,
                    "inputTypes": ["Message"],
                    "type": "str"
                }
        else:
            # Default input field
            return {
                "fieldName": "input_value",
                "id": node_id,
                "inputTypes": ["Data", "Message"],
                "type": "str"
            }

    def _format_handle_string(self, handle_data: Dict[str, Any]) -> str:
        """Format handle data as UI-compatible string with œ delimiters."""
        # Use the safe version for consistency
        result = self._format_handle_string_safe(handle_data)
        if isinstance(result, ErrorResult):
            # Fallback for backward compatibility
            logger.warning("Handle string formatting failed, using fallback")
            return json.dumps(handle_data, separators=(',', ':')).replace('"', 'œ')
        return result

    def _normalize_component_format(self, components: Any) -> List[Tuple[str, Dict[str, Any]]]:
        """Normalize component format to list of (id, data) tuples."""
        if isinstance(components, dict):
            return [(comp_id, comp_data) for comp_id, comp_data in components.items()]
        elif isinstance(components, list):
            return [(comp.get("id", f"component_{i}"), comp) for i, comp in enumerate(components)]
        else:
            return []

    def _find_components_by_type(self, component_mappings: Dict[str, Dict[str, Any]],
                                types: List[str]) -> List[Tuple[str, Dict[str, Any]]]:
        """Find components by Genesis type."""
        found = []
        for comp_id, mapping in component_mappings.items():
            genesis_type = mapping.get("genesis_type", "")
            if genesis_type in types:
                found.append((comp_id, mapping))
        return found

    def _find_tool_components(self, components: Dict[str, Any],
                             component_mappings: Dict[str, Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
        """Find components that can be used as tools."""
        tool_components = []

        component_items = self._normalize_component_format(components)

        for comp_id, comp_data in component_items:
            mapping = component_mappings.get(comp_id)
            if not mapping:
                continue

            genesis_type = mapping.get("genesis_type", "")
            tool_capabilities = mapping.get("tool_capabilities", {})

            # Check if component can provide tools
            if (comp_data.get("asTools", False) or
                tool_capabilities.get("provides_tools", False) or
                genesis_type in ["genesis:api_request"] or
                "connector" in genesis_type):

                tool_components.append((comp_id, mapping))

        return tool_components

    def _should_connect_tool_to_agent(self, tool_comp_id: str, agent_comp_id: str,
                                    components: Dict[str, Any]) -> bool:
        """Determine if a tool should automatically connect to an agent."""
        component_items = self._normalize_component_format(components)
        components_dict = dict(component_items)

        tool_data = components_dict.get(tool_comp_id, {})
        agent_data = components_dict.get(agent_comp_id, {})

        tool_type = tool_data.get("type", "")

        # Healthcare tools should connect to healthcare agents
        if any(term in tool_type for term in ["ehr", "eligibility", "claims", "medical"]):
            agent_config = agent_data.get("config", {})
            system_message = agent_config.get("system_message", "").lower()
            if any(term in system_message for term in ["medical", "health", "patient", "clinical"]):
                return True

        # API tools generally connect to agents
        if tool_type == "genesis:api_request":
            return True

        # Explicitly marked tools
        if tool_data.get("asTools", False):
            return True

        return False

    def _extract_component_id_from_node(self, node_id: str) -> str:
        """Extract component ID from node ID (simplified for now)."""
        return node_id

    def _optimize_connections(self, connections: List[Dict[str, Any]],
                            context: ProcessingContext) -> List[Dict[str, Any]]:
        """Optimize connections by removing duplicates and invalid connections."""
        # Remove duplicates
        unique_connections = []
        connection_keys = set()

        for conn in connections:
            key = (
                conn.get("source"),
                conn.get("target"),
                conn.get("sourceHandle"),
                conn.get("targetHandle")
            )

            if key not in connection_keys:
                connection_keys.add(key)
                unique_connections.append(conn)

        logger.info(f"Optimized connections: {len(connections)} -> {len(unique_connections)} "
                   f"(removed {len(connections) - len(unique_connections)} duplicates)")

        return unique_connections

    def _validate_build_inputs(self,
                             components: Dict[str, Any],
                             component_mappings: Dict[str, Dict[str, Any]],
                             context: ProcessingContext) -> ErrorResult:
        """Validate inputs for build_connections method."""
        errors = []

        if not isinstance(components, (dict, list)):
            error = self.error_handler.create_error(
                operation="validate_build_inputs",
                error_id="invalid_components_type",
                message="Components must be a dictionary or list",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.CRITICAL,
                suggested_fix="Ensure components is a dictionary or list object"
            )
            errors.append(error)

        if not isinstance(component_mappings, dict):
            error = self.error_handler.create_error(
                operation="validate_build_inputs",
                error_id="invalid_mappings_type",
                message="Component mappings must be a dictionary",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.CRITICAL,
                suggested_fix="Ensure component_mappings is a dictionary object"
            )
            errors.append(error)

        if not isinstance(context, ProcessingContext):
            error = self.error_handler.create_error(
                operation="validate_build_inputs",
                error_id="invalid_context_type",
                message="Context must be a ProcessingContext object",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.CRITICAL,
                suggested_fix="Pass a valid ProcessingContext object"
            )
            errors.append(error)

        if errors:
            return ErrorResult.error_result(errors)

        return ErrorResult.success_result(None)

    def _generate_uuid_with_retry(self, node_type: str, component_id: str) -> Union[str, ErrorResult]:
        """Generate UUID with retry logic for reliability."""
        for attempt in range(self.uuid_retry_attempts):
            try:
                generated_uuid = str(uuid.uuid4())

                # Validate the generated UUID
                if not generated_uuid or len(generated_uuid) != 36:
                    raise ValueError(f"Invalid UUID generated: {generated_uuid}")

                return generated_uuid

            except Exception as e:
                if attempt == self.uuid_retry_attempts - 1:
                    # Last attempt failed
                    error = self.error_handler.handle_exception(
                        operation="generate_uuid_with_retry",
                        exception=e,
                        error_id=CommonErrorIds.CONNECTION_UUID_GENERATION_FAILED,
                        category=ErrorCategory.SYSTEM,
                        severity=ErrorSeverity.HIGH,
                        component_id=component_id,
                        field_path=f"{node_type}_uuid",
                        suggested_fix="Check system UUID generation capabilities",
                        retry_possible=True,
                        attempt=attempt + 1,
                        max_attempts=self.uuid_retry_attempts
                    )
                    return ErrorResult.error_result([error])

                # Sleep briefly before retry
                import time
                time.sleep(0.01 * (attempt + 1))

    def _validate_component_type(self, mapping: Dict[str, Any], component_id: str) -> Union[str, ErrorResult]:
        """Validate and extract component type from mapping."""
        try:
            if not isinstance(mapping, dict):
                error = self.error_handler.create_error(
                    operation="validate_component_type",
                    error_id=CommonErrorIds.CONNECTION_INVALID_COMPONENT_TYPE,
                    message=f"Component mapping for {component_id} is not a dictionary",
                    category=ErrorCategory.VALIDATION,
                    severity=ErrorSeverity.HIGH,
                    component_id=component_id,
                    suggested_fix="Ensure component mapping is a valid dictionary"
                )
                return ErrorResult.error_result([error])

            genesis_type = mapping.get("genesis_type", "")
            if not genesis_type:
                error = self.error_handler.create_error(
                    operation="validate_component_type",
                    error_id=CommonErrorIds.CONNECTION_INVALID_COMPONENT_TYPE,
                    message=f"Component {component_id} missing genesis_type in mapping",
                    category=ErrorCategory.VALIDATION,
                    severity=ErrorSeverity.HIGH,
                    component_id=component_id,
                    field_path="genesis_type",
                    suggested_fix="Ensure component mapping includes valid genesis_type"
                )
                return ErrorResult.error_result([error])

            return genesis_type

        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="validate_component_type",
                exception=e,
                error_id=CommonErrorIds.CONNECTION_INVALID_COMPONENT_TYPE,
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.HIGH,
                component_id=component_id,
                retry_possible=False
            )
            return ErrorResult.error_result([error])

    def _create_source_handle_data_safe(self, component_type: str, node_id: str, use_as: str) -> Union[Dict[str, Any], ErrorResult]:
        """Create source handle data with error handling."""
        try:
            return self._create_source_handle_data(component_type, node_id, use_as)
        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="create_source_handle_data",
                exception=e,
                error_id="source_handle_creation_failed",
                category=ErrorCategory.CONNECTION,
                severity=ErrorSeverity.HIGH,
                component_type=component_type,
                node_id=node_id,
                use_as=use_as
            )
            return ErrorResult.error_result([error])

    def _create_target_handle_data_safe(self, component_type: str, node_id: str, use_as: str) -> Union[Dict[str, Any], ErrorResult]:
        """Create target handle data with error handling."""
        try:
            return self._create_target_handle_data(component_type, node_id, use_as)
        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="create_target_handle_data",
                exception=e,
                error_id="target_handle_creation_failed",
                category=ErrorCategory.CONNECTION,
                severity=ErrorSeverity.HIGH,
                component_type=component_type,
                node_id=node_id,
                use_as=use_as
            )
            return ErrorResult.error_result([error])

    def _format_handle_string_safe(self, handle_data: Dict[str, Any]) -> Union[str, ErrorResult]:
        """Format handle string with comprehensive error handling."""
        try:
            # Validate input data
            if not isinstance(handle_data, dict):
                error = self.error_handler.create_error(
                    operation="format_handle_string",
                    error_id=CommonErrorIds.CONNECTION_JSON_FORMATTING_FAILED,
                    message="Handle data must be a dictionary",
                    category=ErrorCategory.DATA,
                    severity=ErrorSeverity.HIGH,
                    suggested_fix="Ensure handle_data is a valid dictionary"
                )
                return ErrorResult.error_result([error])

            # Try JSON serialization with timeout protection
            try:
                json_str = json.dumps(handle_data, separators=(',', ':'), ensure_ascii=True)

                # Validate JSON string
                if not json_str or len(json_str) > 10000:  # Reasonable size limit
                    error = self.error_handler.create_error(
                        operation="format_handle_string",
                        error_id=CommonErrorIds.CONNECTION_JSON_FORMATTING_FAILED,
                        message=f"JSON string invalid or too large: {len(json_str) if json_str else 0} chars",
                        category=ErrorCategory.DATA,
                        severity=ErrorSeverity.HIGH,
                        suggested_fix="Simplify handle data structure"
                    )
                    return ErrorResult.error_result([error])

                # Replace quotes with special delimiter
                formatted_string = json_str.replace('"', 'œ')
                return formatted_string

            except (TypeError, ValueError, OverflowError) as json_error:
                error = self.error_handler.handle_exception(
                    operation="format_handle_string",
                    exception=json_error,
                    error_id=CommonErrorIds.CONNECTION_JSON_FORMATTING_FAILED,
                    category=ErrorCategory.DATA,
                    severity=ErrorSeverity.HIGH,
                    suggested_fix="Check handle data for non-serializable objects",
                    retry_possible=False
                )
                return ErrorResult.error_result([error])

        except Exception as e:
            error = self.error_handler.handle_exception(
                operation="format_handle_string",
                exception=e,
                error_id=CommonErrorIds.CONNECTION_JSON_FORMATTING_FAILED,
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.HIGH,
                retry_possible=True
            )
            return ErrorResult.error_result([error])