from typing import Any

from pydantic import AwareDatetime, BaseModel, EmailStr, Field

# Segment limits normal API requests to 32 KiB. Reserve 2 KiB for the event
# envelope and common fields added by TelemetryService.
MAX_TELEMETRY_PAYLOAD_SIZE = 30 * 1024


class BasePayload(BaseModel):
    client_type: str | None = Field(default=None, serialization_alias="clientType")


class RunPayload(BasePayload):
    run_is_webhook: bool = Field(default=False, serialization_alias="runIsWebhook")
    run_seconds: int = Field(serialization_alias="runSeconds")
    run_success: bool = Field(serialization_alias="runSuccess")
    run_error_message: str = Field("", serialization_alias="runErrorMessage")
    run_id: str | None = Field(None, serialization_alias="runId")
    # Set at the run-event boundary for local consumers; never exported as telemetry.
    run_completed_at: AwareDatetime | None = Field(default=None, exclude=True)


class DeploymentPayload(BasePayload):
    deployment_action: str = Field(serialization_alias="deploymentAction")
    deployment_provider: str = Field(serialization_alias="deploymentProvider")
    deployment_seconds: float = Field(serialization_alias="deploymentSeconds")
    deployment_success: bool = Field(serialization_alias="deploymentSuccess")
    deployment_error_message: str = Field(default="", serialization_alias="deploymentErrorMessage")
    wxo_tenant_id: str | None = Field(default=None, serialization_alias="wxoTenantId")


class IntegrationActionPayload(BasePayload):
    """Low-cardinality integration action event with no connection identifiers."""

    provider: str
    capability: str
    ms: int
    success: bool
    error_code: str | None = Field(None, serialization_alias="errorCode")
    owner_kind: str = Field(serialization_alias="ownerKind")
    principal_kind: str = Field(serialization_alias="principalKind")


class ShutdownPayload(BasePayload):
    time_running: int = Field(serialization_alias="timeRunning")


class EmailPayload(BasePayload):
    email: EmailStr


class VersionPayload(BasePayload):
    package: str
    version: str
    platform: str
    python: str
    arch: str
    auto_login: bool = Field(serialization_alias="autoLogin")
    cache_type: str = Field(serialization_alias="cacheType")
    backend_only: bool = Field(serialization_alias="backendOnly")
    database_dialect: str = Field("unknown", serialization_alias="databaseDialect")


class PlaygroundPayload(BasePayload):
    playground_seconds: int = Field(serialization_alias="playgroundSeconds")
    playground_component_count: int | None = Field(None, serialization_alias="playgroundComponentCount")
    playground_success: bool = Field(serialization_alias="playgroundSuccess")
    playground_error_message: str = Field("", serialization_alias="playgroundErrorMessage")
    playground_run_id: str | None = Field(None, serialization_alias="playgroundRunId")


class ComponentPayload(BasePayload):
    component_name: str = Field(serialization_alias="componentName")
    component_id: str = Field(serialization_alias="componentId")
    component_seconds: int = Field(serialization_alias="componentSeconds")
    component_success: bool = Field(serialization_alias="componentSuccess")
    component_error_message: str | None = Field(None, serialization_alias="componentErrorMessage")
    component_run_id: str | None = Field(None, serialization_alias="componentRunId")


class ComponentInputsPayload(BasePayload):
    """Separate payload for component input values, joined via component_run_id.

    This payload supports automatic splitting when its serialized size exceeds limits:
    - If component_inputs causes the payload to exceed max_payload_size,
      the payload is split into multiple chunks
    - Each chunk includes all fixed fields (component_run_id, component_id, component_name)
      for analytics join
    - Input fields are distributed across chunks to respect size limits
    - Chunks include chunk_index and total_chunks metadata for reassembly
    - Single oversized fields are truncated with "...[truncated]" marker

    Usage:
        payload = ComponentInputsPayload(
            component_run_id="run-123",
            component_name="MyComponent",
            component_inputs={"input1": "value1", "input2": "value2"}
        )
        chunks = payload.split_if_needed()
        # Returns list of 1+ payloads, all respecting size limit
    """

    component_run_id: str = Field(serialization_alias="componentRunId")
    component_id: str = Field(serialization_alias="componentId")
    component_name: str = Field(serialization_alias="componentName")
    component_inputs: dict[str, Any] = Field(serialization_alias="componentInputs")
    chunk_index: int | None = Field(None, serialization_alias="chunkIndex")
    total_chunks: int | None = Field(None, serialization_alias="totalChunks")

    def _calculate_payload_size(self) -> int:
        """Return the UTF-8 byte size of the serialized JSON payload."""
        import orjson

        payload_dict = self.model_dump(by_alias=True, exclude_none=True, exclude_unset=True)
        return len(orjson.dumps(payload_dict))

    def _truncate_value_to_fit(self, key: str, value: Any, max_payload_size: int) -> Any:
        """Truncate a value using binary search to fit within max_payload_size.

        Args:
            key: The field key
            value: The field value to truncate
            max_payload_size: Maximum serialized payload size in bytes

        Returns:
            Truncated value with "...[truncated]" suffix
        """
        truncation_suffix = "...[truncated]"

        # Convert to string if needed (handles both string and non-string values)
        # For string values: truncate directly
        # For non-string values: convert to string representation, then truncate
        str_value = value if isinstance(value, str) else str(value)

        # Use binary search to find optimal truncation point
        # Find the longest prefix that keeps the serialized payload within the budget.
        max_len = len(str_value)
        min_len = 0
        truncated_value = str_value[:100] + truncation_suffix  # Initial guess

        while min_len < max_len:
            mid_len = (min_len + max_len + 1) // 2
            test_val = str_value[:mid_len] + truncation_suffix
            test_inputs = {key: test_val}
            test_payload = ComponentInputsPayload(
                component_run_id=self.component_run_id,
                component_id=self.component_id,
                component_name=self.component_name,
                component_inputs=test_inputs,
                chunk_index=0,
                total_chunks=1,
            )

            if test_payload._calculate_payload_size() <= max_payload_size:
                truncated_value = test_val
                min_len = mid_len
            else:
                max_len = mid_len - 1

        return truncated_value

    def split_if_needed(self, max_payload_size: int = MAX_TELEMETRY_PAYLOAD_SIZE) -> list["ComponentInputsPayload"]:
        """Split payload into multiple chunks if its JSON exceeds max_payload_size.

        Args:
            max_payload_size: Maximum serialized payload size in bytes

        Returns:
            List of ComponentInputsPayload objects. Single item if no split needed,
            multiple items if payload was split across chunks.
        """
        from lfx.log.logger import logger

        current_size = self._calculate_payload_size()

        # If fits within limit, return as-is
        if current_size <= max_payload_size:
            return [self]

        # Need to split - check if component_inputs is a dict
        if not isinstance(self.component_inputs, dict):
            # If not a dict, return as-is (fail-safe)
            logger.warning(f"component_inputs is not a dict, cannot split: {type(self.component_inputs)}")
            return [self]

        if not self.component_inputs:
            # Empty inputs, return as-is
            return [self]

        # Distribute input fields across chunks
        chunks_data = []
        current_chunk_inputs: dict[str, Any] = {}

        for key, value in self.component_inputs.items():
            # Calculate size if we add this field to current chunk
            test_inputs = {**current_chunk_inputs, key: value}
            test_payload = ComponentInputsPayload(
                component_run_id=self.component_run_id,
                component_id=self.component_id,
                component_name=self.component_name,
                component_inputs=test_inputs,
                chunk_index=0,
                total_chunks=1,
            )
            test_size = test_payload._calculate_payload_size()

            # If adding this field exceeds limit, start new chunk
            if test_size > max_payload_size and current_chunk_inputs:
                chunks_data.append(current_chunk_inputs)
                # Check if the field by itself exceeds the limit
                single_field_test = ComponentInputsPayload(
                    component_run_id=self.component_run_id,
                    component_id=self.component_id,
                    component_name=self.component_name,
                    component_inputs={key: value},
                    chunk_index=0,
                    total_chunks=1,
                )
                if single_field_test._calculate_payload_size() > max_payload_size:
                    # Single field is too large - truncate it
                    logger.warning(f"Truncating oversized field '{key}' in component_inputs")
                    truncated_value = self._truncate_value_to_fit(key, value, max_payload_size)
                    current_chunk_inputs = {key: truncated_value}
                else:
                    current_chunk_inputs = {key: value}
            elif test_size > max_payload_size and not current_chunk_inputs:
                # Single field is too large - truncate it
                logger.warning(f"Truncating oversized field '{key}' in component_inputs")

                # Binary search to find max value length that fits
                truncated_value = self._truncate_value_to_fit(key, value, max_payload_size)
                current_chunk_inputs[key] = truncated_value
            else:
                current_chunk_inputs[key] = value

        # Add final chunk
        if current_chunk_inputs:
            chunks_data.append(current_chunk_inputs)

        # Create chunk payloads
        total_chunks = len(chunks_data)
        result = []

        for chunk_index, chunk_inputs in enumerate(chunks_data):
            chunk_payload = ComponentInputsPayload(
                component_run_id=self.component_run_id,
                component_id=self.component_id,
                component_name=self.component_name,
                component_inputs=chunk_inputs,
                chunk_index=chunk_index,
                total_chunks=total_chunks,
            )
            result.append(chunk_payload)

        return result


class ExceptionPayload(BasePayload):
    exception_type: str = Field(serialization_alias="exceptionType")
    exception_message: str = Field(serialization_alias="exceptionMessage")
    exception_context: str = Field(serialization_alias="exceptionContext")  # "lifespan" or "handler"
    stack_trace_hash: str | None = Field(None, serialization_alias="stackTraceHash")  # Hash for grouping


class ComponentIndexPayload(BasePayload):
    index_source: str = Field(serialization_alias="indexSource")  # "builtin", "cache", or "dynamic"
    num_modules: int = Field(serialization_alias="numModules")
    num_components: int = Field(serialization_alias="numComponents")
    dev_mode: bool = Field(serialization_alias="devMode")
    filtered_modules: str | None = Field(None, serialization_alias="filteredModules")  # CSV if filtering
    load_time_ms: int = Field(serialization_alias="loadTimeMs")
