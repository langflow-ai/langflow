package org.langflow.sdk.v2.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;
import java.util.Map;

/**
 * Request and response types for Langflow API v2 workflows.
 */
public final class V2Models {
    private V2Models() {
    }

    public enum JobStatus {queued, in_progress, completed, failed, cancelled, timed_out}

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record WorkflowRequest(boolean background, boolean stream,
                                  @JsonProperty("flow_id") String flowId,
                                  Map<String, Object> inputs, Map<String, String> globals) {
        public WorkflowRequest {
            if (flowId == null || flowId.isBlank()) {
                throw new IllegalArgumentException("flowId is required");
            }
            if (background && stream) {
                throw new IllegalArgumentException("background and stream cannot both be true");
            }
            globals = globals == null ? Map.of() : Map.copyOf(globals);
        }

        public static WorkflowRequest synchronous(String flowId, Map<String, Object> inputs) {
            return new WorkflowRequest(false, false, flowId, inputs, Map.of());
        }

        public static WorkflowRequest background(String flowId, Map<String, Object> inputs) {
            return new WorkflowRequest(true, false, flowId, inputs, Map.of());
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ErrorDetail(String error, String code, Map<String, Object> details) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ComponentOutput(String type, JobStatus status, JsonNode content, Map<String, Object> metadata) {
    }

    public sealed interface WorkflowResult permits WorkflowResponse, WorkflowJob {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowResponse(@JsonProperty("flow_id") String flowId,
                                   @JsonProperty("job_id") String jobId, String object,
                                   @JsonProperty("created_timestamp") String createdTimestamp,
                                   JobStatus status, List<ErrorDetail> errors, Map<String, Object> inputs,
                                   Map<String, String> globals, Map<String, ComponentOutput> outputs)
            implements WorkflowResult {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowJob(@JsonProperty("job_id") String jobId,
                              @JsonProperty("flow_id") String flowId, String object,
                              @JsonProperty("created_timestamp") String createdTimestamp,
                              JobStatus status, Map<String, String> links, List<ErrorDetail> errors,
                              Map<String, String> globals) implements WorkflowResult {
    }

    public record WorkflowStopRequest(@JsonProperty("job_id") String jobId) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WorkflowStopResponse(@JsonProperty("job_id") String jobId, String message) {
    }
}
