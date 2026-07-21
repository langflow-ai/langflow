package org.langflow.sdk.v1.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Request and response types for Langflow API v1.
 */
public final class V1Models {
    private V1Models() {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record FlowCreate(String name, String description, Map<String, Object> data,
                             @JsonProperty("is_component") Boolean isComponent,
                             @JsonProperty("endpoint_name") String endpointName, List<String> tags,
                             @JsonProperty("folder_id") UUID folderId, String icon,
                             @JsonProperty("icon_bg_color") String iconBgColor, Boolean locked,
                             @JsonProperty("mcp_enabled") Boolean mcpEnabled) {
        public FlowCreate(String name) {
            this(name, null, null, false, null, null, null, null, null, false, false);
        }
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record FlowUpdate(String name, String description, Map<String, Object> data,
                             @JsonProperty("endpoint_name") String endpointName, List<String> tags,
                             @JsonProperty("folder_id") UUID folderId, String icon,
                             @JsonProperty("icon_bg_color") String iconBgColor, Boolean locked,
                             @JsonProperty("mcp_enabled") Boolean mcpEnabled) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Flow(UUID id, String name, String description, Map<String, Object> data,
                       @JsonProperty("is_component") boolean isComponent,
                       @JsonProperty("updated_at") OffsetDateTime updatedAt,
                       @JsonProperty("endpoint_name") String endpointName, List<String> tags,
                       @JsonProperty("folder_id") UUID folderId, @JsonProperty("user_id") UUID userId,
                       String icon, @JsonProperty("icon_bg_color") String iconBgColor, boolean locked,
                       @JsonProperty("mcp_enabled") boolean mcpEnabled, boolean webhook,
                       @JsonProperty("access_type") String accessType) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record ProjectCreate(String name, String description,
                                @JsonProperty("flows_list") List<UUID> flowsList,
                                @JsonProperty("components_list") List<UUID> componentsList) {
        public ProjectCreate(String name) {
            this(name, null, null, null);
        }
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record ProjectUpdate(String name, String description) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Project(UUID id, String name, String description, @JsonProperty("parent_id") UUID parentId) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ProjectWithFlows(UUID id, String name, String description,
                                   @JsonProperty("parent_id") UUID parentId, List<Flow> flows) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record RunRequest(@JsonProperty("input_value") String inputValue,
                             @JsonProperty("input_type") String inputType,
                             @JsonProperty("output_type") String outputType,
                             Map<String, Object> tweaks, boolean stream) {
        public RunRequest(String inputValue) {
            this(inputValue, "chat", "chat", null, false);
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record RunOutput(Map<String, Object> results, Map<String, Object> artifacts,
                            List<Map<String, Object>> outputs, @JsonProperty("session_id") String sessionId,
                            Double timedelta) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record RunResponse(@JsonProperty("session_id") String sessionId, List<RunOutput> outputs) {
        public String firstTextOutput() {
            if (outputs == null) {
                return null;
            }
            for (RunOutput block : outputs) {
                if (block.outputs() == null) {
                    continue;
                }
                for (Map<String, Object> component : block.outputs()) {
                    Object raw = component.get("results");
                    if (!(raw instanceof Map<?, ?> results)) {
                        continue;
                    }
                    Object message = results.get("message");
                    if (message instanceof Map<?, ?> msg && msg.get("text") != null) {
                        return msg.get("text").toString();
                    }
                    if (results.get("text") != null) {
                        return results.get("text").toString();
                    }
                }
            }
            return null;
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record StreamChunk(String event, JsonNode data) {
        public String text() {
            if (data == null) {
                return null;
            }
            if ("add_message".equals(event)) {
                return data.path("message").path("text").isMissingNode()
                        ? null : data.path("message").path("text").asText();
            }
            JsonNode token = data.get("chunk");
            if (token == null) {
                token = data.get("token");
            }
            return token == null || token.isNull() ? null : token.asText();
        }

        public boolean isToken() {
            return "token".equals(event);
        }

        public boolean isEnd() {
            return "end".equals(event);
        }

        public boolean isError() {
            return "error".equals(event);
        }
    }

    public record UpsertResult(Flow flow, boolean created) {
    }
}
