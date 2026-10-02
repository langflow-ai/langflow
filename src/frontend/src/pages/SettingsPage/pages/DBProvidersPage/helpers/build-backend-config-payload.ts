import {
  type AvailableDBProviderId,
  OPENSEARCH_VARIABLES,
} from "@/constants/dbProviderConstants";

// Build a ``backend_config`` payload for ``POST /test-connection`` from
// the in-memory form values, side-stepping the global-variable cache
// which is stale immediately after Save. The server-side test still
// resolves credentials (URL/USERNAME/PASSWORD) through variable_service
// using the variable-name fields below — those names are stable
// constants and don't depend on what the user typed.
export function buildBackendConfigPayload(
  providerId: AvailableDBProviderId,
  literalFields: Record<string, string>,
  booleanFields: Record<string, boolean>,
): Record<string, unknown> {
  if (providerId !== "opensearch") {
    return {};
  }
  return {
    url_variable: OPENSEARCH_VARIABLES.URL,
    username_variable: OPENSEARCH_VARIABLES.USERNAME,
    password_variable: OPENSEARCH_VARIABLES.PASSWORD,
    index_name: literalFields[OPENSEARCH_VARIABLES.INDEX_NAME] || "",
    vector_field:
      literalFields[OPENSEARCH_VARIABLES.VECTOR_FIELD] || "vector_field",
    text_field: literalFields[OPENSEARCH_VARIABLES.TEXT_FIELD] || "text",
    use_ssl: booleanFields[OPENSEARCH_VARIABLES.USE_SSL] ?? true,
    verify_certs: booleanFields[OPENSEARCH_VARIABLES.VERIFY_CERTS] ?? true,
  };
}
