import {
  ACTIVE_DB_PROVIDER_VARIABLE,
  getActiveDBProvider,
  getDefaultDBProviderConfig,
  isDBProviderConfigured,
  OPENSEARCH_VARIABLES,
} from "../dbProviderConstants";

const variable = (name: string, value: string) => ({
  id: name,
  name,
  value,
  type: "Generic" as const,
  default_fields: [],
});

describe("dbProviderConstants", () => {
  it("defaults to Chroma when no provider is configured", () => {
    expect(getActiveDBProvider([])).toBe("chroma");
    expect(getDefaultDBProviderConfig([])).toEqual({
      backendType: "chroma",
      backendConfig: {},
    });
  });

  it("falls back to Chroma for unsupported configured provider values", () => {
    expect(
      getActiveDBProvider([variable(ACTIVE_DB_PROVIDER_VARIABLE, "astra")]),
    ).toBe("chroma");
  });

  it("builds OpenSearch provider config from saved global variables", () => {
    expect(
      getDefaultDBProviderConfig([
        variable(ACTIVE_DB_PROVIDER_VARIABLE, "opensearch"),
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
        // Defaults when no toggle has been saved.
        use_ssl: true,
        verify_certs: true,
      },
    });
  });

  it("emits SSL toggle booleans from stored global variables", () => {
    expect(
      getDefaultDBProviderConfig([
        variable(ACTIVE_DB_PROVIDER_VARIABLE, "opensearch"),
        variable(OPENSEARCH_VARIABLES.INDEX_NAME, "kb-index"),
        variable(OPENSEARCH_VARIABLES.USE_SSL, "false"),
        variable(OPENSEARCH_VARIABLES.VERIFY_CERTS, "false"),
      ]).backendConfig,
    ).toMatchObject({
      use_ssl: false,
      verify_certs: false,
    });
  });

  it("treats unrecognized SSL variable values as the default", () => {
    expect(
      getDefaultDBProviderConfig([
        variable(ACTIVE_DB_PROVIDER_VARIABLE, "opensearch"),
        variable(OPENSEARCH_VARIABLES.INDEX_NAME, "kb-index"),
        variable(OPENSEARCH_VARIABLES.USE_SSL, "yeah"),
        variable(OPENSEARCH_VARIABLES.VERIFY_CERTS, "1"),
      ]).backendConfig,
    ).toMatchObject({
      use_ssl: true, // garbage falls back to default (true)
      verify_certs: true, // "1" parses as true
    });
  });

  it("requires OpenSearch required settings before it can be selected", () => {
    expect(
      isDBProviderConfigured("opensearch", [
        variable(OPENSEARCH_VARIABLES.INDEX_NAME, "kb-index"),
      ]),
    ).toBe(false);

    // URL + index alone is no longer enough — basic-auth credentials
    // are required so the settings UI matches the runtime contract
    // (the OpenSearch components default to basic auth and reject a
    // run with empty username/password).
    expect(
      isDBProviderConfigured("opensearch", [
        variable(OPENSEARCH_VARIABLES.URL, "https://search.example.com:9200"),
        variable(OPENSEARCH_VARIABLES.INDEX_NAME, "kb-index"),
      ]),
    ).toBe(false);

    expect(
      isDBProviderConfigured("opensearch", [
        variable(OPENSEARCH_VARIABLES.URL, "https://search.example.com:9200"),
        variable(OPENSEARCH_VARIABLES.USERNAME, "admin"),
        variable(OPENSEARCH_VARIABLES.PASSWORD, "secret"),
        variable(OPENSEARCH_VARIABLES.INDEX_NAME, "kb-index"),
      ]),
    ).toBe(true);
  });

  it("flags OpenSearch as not-configured when only one of username/password is set", () => {
    // Asymmetric credentials are a footgun: the backend treats
    // ``http_auth`` as a tuple of (username, password) and falls back
    // to no-auth when only one is set, which silently masquerades as
    // success against auth-disabled clusters but fails against real
    // ones. Force both fields to be present.
    expect(
      isDBProviderConfigured("opensearch", [
        variable(OPENSEARCH_VARIABLES.URL, "https://search.example.com:9200"),
        variable(OPENSEARCH_VARIABLES.USERNAME, "admin"),
        variable(OPENSEARCH_VARIABLES.INDEX_NAME, "kb-index"),
      ]),
    ).toBe(false);
  });
});
