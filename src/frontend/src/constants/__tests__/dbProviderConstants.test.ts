import {
  ACTIVE_DB_PROVIDER_VARIABLE,
  CHROMA_CLOUD_VARIABLES,
  getActiveDBProvider,
  getDefaultDBProviderConfig,
  isDBProviderConfigured,
  OPENSEARCH_VARIABLES,
} from "../dbProviderConstants";

const variable = (
  name: string,
  value: string | undefined,
  type: "Credential" | "Generic" = "Generic",
  hasValue?: boolean,
) => ({
  id: name,
  name,
  value,
  type,
  default_fields: [],
  has_value: hasValue,
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
    const config = getDefaultDBProviderConfig([
      variable(ACTIVE_DB_PROVIDER_VARIABLE, "opensearch"),
      variable(OPENSEARCH_VARIABLES.URL, "https://search.example.com:9200"),
      variable(OPENSEARCH_VARIABLES.USERNAME, "admin"),
      variable(OPENSEARCH_VARIABLES.PASSWORD, undefined, "Credential", true),
      // Even when a global index name is set, it must NOT be copied into a
      // base's config — every KB/MB derives its own per-base index server-side,
      // so pinning a shared literal here would re-mix vectors across bases.
      variable(OPENSEARCH_VARIABLES.INDEX_NAME, "kb-index"),
      variable(OPENSEARCH_VARIABLES.VECTOR_FIELD, "embedding"),
      variable(OPENSEARCH_VARIABLES.TEXT_FIELD, "content"),
    ]);
    expect(config).toEqual({
      backendType: "opensearch",
      backendConfig: {
        url_variable: OPENSEARCH_VARIABLES.URL,
        username_variable: OPENSEARCH_VARIABLES.USERNAME,
        password_variable: OPENSEARCH_VARIABLES.PASSWORD,
        vector_field: "embedding",
        text_field: "content",
        // Defaults when no toggle has been saved.
        use_ssl: true,
        verify_certs: true,
      },
    });
    expect(config.backendConfig).not.toHaveProperty("index_name");
  });

  it("emits SSL toggle booleans from stored global variables", () => {
    expect(
      getDefaultDBProviderConfig([
        variable(ACTIVE_DB_PROVIDER_VARIABLE, "opensearch"),
        variable(OPENSEARCH_VARIABLES.URL, "https://search.example.com:9200"),
        variable(OPENSEARCH_VARIABLES.USERNAME, "admin"),
        variable(OPENSEARCH_VARIABLES.PASSWORD, undefined, "Credential", true),
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
        variable(OPENSEARCH_VARIABLES.URL, "https://search.example.com:9200"),
        variable(OPENSEARCH_VARIABLES.USERNAME, "admin"),
        variable(OPENSEARCH_VARIABLES.PASSWORD, undefined, "Credential", true),
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
    // The index name is no longer a gating field — the index is created
    // lazily per-KB/MB at base-creation time, so it must not block enabling
    // OpenSearch. URL + basic-auth credentials are what's actually required.
    expect(isDBProviderConfigured("opensearch", [])).toBe(false);

    // URL alone is not enough — basic-auth credentials are required so the
    // settings UI matches the runtime contract (the OpenSearch components
    // default to basic auth and reject a run with empty username/password).
    expect(
      isDBProviderConfigured("opensearch", [
        variable(OPENSEARCH_VARIABLES.URL, "https://search.example.com:9200"),
      ]),
    ).toBe(false);

    // URL + credentials, with NO index name, is now sufficient.
    expect(
      isDBProviderConfigured("opensearch", [
        variable(OPENSEARCH_VARIABLES.URL, "https://search.example.com:9200"),
        variable(OPENSEARCH_VARIABLES.USERNAME, "admin"),
        variable(OPENSEARCH_VARIABLES.PASSWORD, "secret"),
      ]),
    ).toBe(true);
  });

  it("requires a stored Chroma Cloud credential value", () => {
    const blankCredential = variable(
      CHROMA_CLOUD_VARIABLES.API_KEY,
      undefined,
      "Credential",
      false,
    );
    expect(isDBProviderConfigured("chroma_cloud", [blankCredential])).toBe(
      false,
    );

    const configuredCredential = variable(
      CHROMA_CLOUD_VARIABLES.API_KEY,
      undefined,
      "Credential",
      true,
    );
    expect(isDBProviderConfigured("chroma_cloud", [configuredCredential])).toBe(
      true,
    );
  });

  it("fails closed for credential variables that omit has_value", () => {
    // A response lacking `has_value` can't distinguish a stored secret from a
    // stale empty row, so the credential must not count as configured.
    const legacyCredential = variable(
      CHROMA_CLOUD_VARIABLES.API_KEY,
      undefined,
      "Credential",
    );
    expect(isDBProviderConfigured("chroma_cloud", [legacyCredential])).toBe(
      false,
    );
  });

  it("falls back to Chroma Local when the active remote provider is no longer configured", () => {
    const variables = [
      variable(ACTIVE_DB_PROVIDER_VARIABLE, "chroma_cloud"),
      variable(CHROMA_CLOUD_VARIABLES.API_KEY, undefined, "Credential", false),
    ];

    expect(getActiveDBProvider(variables)).toBe("chroma");
    expect(getDefaultDBProviderConfig(variables)).toEqual({
      backendType: "chroma",
      backendConfig: {},
    });
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
      ]),
    ).toBe(false);
  });

  it("allows explicit Postgres selection only after it is active", () => {
    expect(isDBProviderConfigured("postgres", [])).toBe(false);
    expect(
      isDBProviderConfigured("postgres", [
        variable(ACTIVE_DB_PROVIDER_VARIABLE, "postgres"),
      ]),
    ).toBe(true);
  });

  describe("when local vector storage is unavailable (production profile)", () => {
    const localUnavailable = false;

    it("reports local Chroma as not configured", () => {
      // Chroma is configured unconditionally when local storage is allowed…
      expect(isDBProviderConfigured("chroma", [])).toBe(true);
      // …but the production profile can't host it on the serving box's disk,
      // so it must read as unconfigured — that's what disables it in pickers
      // and blocks create-time validation instead of a server-side 422.
      expect(isDBProviderConfigured("chroma", [], localUnavailable)).toBe(
        false,
      );
    });

    it("falls back to Postgres instead of Chroma", () => {
      expect(getActiveDBProvider([], localUnavailable)).toBe("postgres");
      expect(getDefaultDBProviderConfig([], localUnavailable)).toEqual({
        backendType: "postgres",
        backendConfig: {},
      });
    });

    it("still honors an explicitly configured remote provider", () => {
      const variables = [
        variable(ACTIVE_DB_PROVIDER_VARIABLE, "opensearch"),
        variable(OPENSEARCH_VARIABLES.URL, "https://search.example.com:9200"),
        variable(OPENSEARCH_VARIABLES.USERNAME, "admin"),
        variable(OPENSEARCH_VARIABLES.PASSWORD, "secret"),
      ];
      expect(getActiveDBProvider(variables, localUnavailable)).toBe(
        "opensearch",
      );
    });

    it("falls back to Postgres even when the active variable pins Chroma", () => {
      // An explicit ``LANGFLOW_KNOWLEDGE_BACKEND=chroma`` must not resurrect a
      // Chroma the create endpoint rejects on the production profile.
      const variables = [variable(ACTIVE_DB_PROVIDER_VARIABLE, "chroma")];
      expect(getActiveDBProvider(variables, localUnavailable)).toBe("postgres");
    });
  });
});
