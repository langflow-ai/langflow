import {
  ACTIVE_KNOWLEDGE_BACKEND_VARIABLE,
  getActiveKnowledgeBackend,
  getDefaultKnowledgeBackendConfig,
  isKnowledgeBackendConfigured,
  OPENSEARCH_VARIABLES,
} from "../knowledgeBackendConstants";

const variable = (name: string, value: string) => ({
  id: name,
  name,
  value,
  type: "Generic" as const,
  default_fields: [],
});

describe("knowledgeBackendConstants", () => {
  it("defaults to Chroma when no backend is configured", () => {
    expect(getActiveKnowledgeBackend([])).toBe("chroma");
    expect(getDefaultKnowledgeBackendConfig([])).toEqual({
      backendType: "chroma",
      backendConfig: {},
    });
  });

  it("falls back to Chroma for unsupported configured backend values", () => {
    expect(
      getActiveKnowledgeBackend([
        variable(ACTIVE_KNOWLEDGE_BACKEND_VARIABLE, "astra"),
      ]),
    ).toBe("chroma");
  });

  it("builds OpenSearch backend config from saved global variables", () => {
    expect(
      getDefaultKnowledgeBackendConfig([
        variable(ACTIVE_KNOWLEDGE_BACKEND_VARIABLE, "opensearch"),
        variable(OPENSEARCH_VARIABLES.INDEX_NAME, "kb-index"),
        variable(OPENSEARCH_VARIABLES.VECTOR_FIELD, "embedding"),
        variable(OPENSEARCH_VARIABLES.TEXT_FIELD, "content"),
      ]),
    ).toEqual({
      backendType: "opensearch",
      backendConfig: {
        url_variable: OPENSEARCH_VARIABLES.URL,
        username_variable: OPENSEARCH_VARIABLES.USERNAME,
        password_variable: OPENSEARCH_VARIABLES.PASSWORD,
        index_name: "kb-index",
        vector_field: "embedding",
        text_field: "content",
      },
    });
  });

  it("requires OpenSearch required settings before it can be selected", () => {
    expect(
      isKnowledgeBackendConfigured("opensearch", [
        variable(OPENSEARCH_VARIABLES.INDEX_NAME, "kb-index"),
      ]),
    ).toBe(false);

    expect(
      isKnowledgeBackendConfigured("opensearch", [
        variable(OPENSEARCH_VARIABLES.URL, "https://search.example.com:9200"),
        variable(OPENSEARCH_VARIABLES.INDEX_NAME, "kb-index"),
      ]),
    ).toBe(true);
  });
});
