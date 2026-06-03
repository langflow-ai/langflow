import type { GlobalVariable } from "@/types/global_variables";

// The stored value (env-var key) intentionally keeps its legacy name so
// existing user installations continue to read the same global variable
// after the UI rename from "Knowledge Backends" to "DB Providers".
export const ACTIVE_DB_PROVIDER_VARIABLE = "LANGFLOW_KNOWLEDGE_BACKEND";

export const OPENSEARCH_VARIABLES = {
  URL: "OPENSEARCH_URL",
  USERNAME: "OPENSEARCH_USERNAME",
  PASSWORD: "OPENSEARCH_PASSWORD", // pragma: allowlist secret
  INDEX_NAME: "OPENSEARCH_INDEX_NAME",
  VECTOR_FIELD: "OPENSEARCH_VECTOR_FIELD",
  TEXT_FIELD: "OPENSEARCH_TEXT_FIELD",
  // Boolean toggles for TLS connection behavior. Persisted as
  // "true"/"false" strings via the global-variable pipeline and
  // coerced back to booleans inside ``getDBProviderConfig``.
  USE_SSL: "OPENSEARCH_USE_SSL",
  VERIFY_CERTS: "OPENSEARCH_VERIFY_CERTS",
} as const;

export const CHROMA_CLOUD_VARIABLES = {
  TENANT: "CHROMA_TENANT",
  DATABASE: "CHROMA_DATABASE",
  API_KEY: "CHROMA_API_KEY", // pragma: allowlist secret
  REGION: "CHROMA_REGION",
} as const;

export type DBProviderId =
  | "chroma"
  | "chroma_cloud"
  | "opensearch"
  | "astra"
  | "mongodb"
  | "postgres";

export type AvailableDBProviderId = Extract<
  DBProviderId,
  "chroma" | "chroma_cloud" | "opensearch"
>;

export interface DBProviderTextField {
  kind?: "text";
  label: string;
  variableKey: string;
  required: boolean;
  isSecret: boolean;
  placeholder: string;
  defaultValue?: string;
}

export interface DBProviderBooleanField {
  kind: "boolean";
  label: string;
  variableKey: string;
  helperText?: string;
  defaultValue: boolean;
}

export type DBProviderConfigField =
  | DBProviderTextField
  | DBProviderBooleanField;

export interface DBProviderOption {
  id: DBProviderId;
  label: string;
  description: string;
  icon: string;
  status: "available" | "coming_soon";
  defaultEnabled?: boolean;
  configFields: DBProviderConfigField[];
}

export const DB_PROVIDER_OPTIONS: DBProviderOption[] = [
  {
    id: "chroma",
    label: "Chroma Local",
    description:
      "Local vector storage bundled with Langflow. No additional configuration required.",
    icon: "Chroma",
    status: "available",
    defaultEnabled: true,
    configFields: [],
  },
  {
    id: "chroma_cloud",
    label: "Chroma Cloud",
    description: "Managed Chroma Cloud vector storage via api.trychroma.com.",
    icon: "Chroma",
    status: "available",
    configFields: [
      {
        label: "API Key",
        variableKey: CHROMA_CLOUD_VARIABLES.API_KEY,
        required: true,
        isSecret: true,
        placeholder: "ck-…",
      },
      {
        label: "Tenant",
        variableKey: CHROMA_CLOUD_VARIABLES.TENANT,
        required: false,
        isSecret: false,
        placeholder: "default-tenant",
      },
      {
        label: "Database",
        variableKey: CHROMA_CLOUD_VARIABLES.DATABASE,
        required: false,
        isSecret: false,
        placeholder: "default-database",
      },
      {
        label: "Region",
        variableKey: CHROMA_CLOUD_VARIABLES.REGION,
        required: false,
        isSecret: false,
        placeholder: "us-east-1",
        defaultValue: "us-east-1",
      },
    ],
  },
  {
    id: "opensearch",
    label: "OpenSearch",
    description:
      "External OpenSearch k-NN index for self-hosted or managed clusters.",
    icon: "OpenSearch",
    status: "available",
    configFields: [
      {
        label: "Cluster URL",
        variableKey: OPENSEARCH_VARIABLES.URL,
        required: true,
        isSecret: false,
        placeholder: "https://search.example.com:9200",
      },
      {
        // Required because the runtime OpenSearch components (KB +
        // canvas vector-store) default to basic auth and surface a
        // confusing "Auth Mode is 'basic' but username/password are
        // missing" error when the global variables aren't populated.
        // Operators with auth-less clusters or external auth (sigv4 /
        // upstream proxy) can set these env vars to a placeholder
        // value; OpenSearch ignores the credentials when auth is not
        // enforced.
        label: "Username",
        variableKey: OPENSEARCH_VARIABLES.USERNAME,
        required: true,
        isSecret: false,
        placeholder: "admin",
      },
      {
        label: "Password",
        variableKey: OPENSEARCH_VARIABLES.PASSWORD,
        required: true,
        isSecret: true,
        placeholder: "Enter OpenSearch password",
      },
      {
        label: "Default index name",
        variableKey: OPENSEARCH_VARIABLES.INDEX_NAME,
        required: true,
        isSecret: false,
        placeholder: "langflow_knowledge",
      },
      {
        // LangChain's OpenSearchVectorSearch stores KB embeddings under
        // ``vector_field`` (its hardwired default), so that is the field the
        // backend reads them back from. Defaulting elsewhere persisted a
        // never-written name and left ``include_embeddings`` retrieval empty.
        label: "Vector field",
        variableKey: OPENSEARCH_VARIABLES.VECTOR_FIELD,
        required: false,
        isSecret: false,
        placeholder: "vector_field",
        defaultValue: "vector_field",
      },
      {
        label: "Text field",
        variableKey: OPENSEARCH_VARIABLES.TEXT_FIELD,
        required: false,
        isSecret: false,
        placeholder: "text",
        defaultValue: "text",
      },
      {
        kind: "boolean",
        label: "Use TLS (HTTPS)",
        variableKey: OPENSEARCH_VARIABLES.USE_SSL,
        helperText:
          "Connect over HTTPS. Disable for plain-HTTP clusters. Defaults to the URL scheme when unset.",
        defaultValue: true,
      },
      {
        kind: "boolean",
        label: "Verify TLS certificate",
        variableKey: OPENSEARCH_VARIABLES.VERIFY_CERTS,
        helperText:
          "Disable for self-signed certificates (the default OpenSearch container ships one).",
        defaultValue: true,
      },
    ],
  },
  {
    id: "astra",
    label: "Astra DB",
    description: "Managed Cassandra vector storage.",
    icon: "AstraDB",
    status: "coming_soon",
    configFields: [],
  },
  {
    id: "mongodb",
    label: "MongoDB Atlas",
    description: "Atlas Vector Search backend.",
    icon: "MongoDB",
    status: "coming_soon",
    configFields: [],
  },
  {
    id: "postgres",
    label: "Postgres pgvector",
    description: "Postgres-backed vector storage.",
    icon: "Postgres",
    status: "coming_soon",
    configFields: [],
  },
];

export const AVAILABLE_DB_PROVIDER_OPTIONS = DB_PROVIDER_OPTIONS.filter(
  (
    provider,
  ): provider is DBProviderOption & {
    id: AvailableDBProviderId;
  } => provider.status === "available",
);

export function getGlobalVariableValue(
  variables: GlobalVariable[],
  name: string,
): string | undefined {
  const value = variables.find((variable) => variable.name === name)?.value;
  return typeof value === "string" && value.trim() ? value : undefined;
}

/**
 * Parse a global-variable value as a boolean. Accepts "true"/"false"
 * (case-insensitive) and the numeric "1"/"0" forms; falls back to
 * ``defaultValue`` for anything else (including "" / undefined).
 *
 * Centralized here so the settings page and the KB-config resolver
 * agree on what a stored "true" means — silently treating "false" as
 * ``Boolean("false") === true`` was the original Python footgun this
 * pipeline replaces.
 */
export function parseBooleanGlobalVariable(
  variables: GlobalVariable[],
  name: string,
  defaultValue: boolean,
): boolean {
  const raw = getGlobalVariableValue(variables, name);
  if (raw === undefined) return defaultValue;
  const normalized = raw.trim().toLowerCase();
  if (normalized === "true" || normalized === "1") return true;
  if (normalized === "false" || normalized === "0") return false;
  return defaultValue;
}

export function getActiveDBProvider(
  variables: GlobalVariable[],
): AvailableDBProviderId {
  const configuredProvider = getGlobalVariableValue(
    variables,
    ACTIVE_DB_PROVIDER_VARIABLE,
  );
  if (configuredProvider === "opensearch") return "opensearch";
  if (configuredProvider === "chroma_cloud") return "chroma_cloud";
  return "chroma";
}

export function getDBProviderOption(
  providerId: DBProviderId | string | undefined,
): DBProviderOption {
  return (
    DB_PROVIDER_OPTIONS.find((provider) => provider.id === providerId) ??
    DB_PROVIDER_OPTIONS[0]
  );
}

export type DBProviderConfigValue = string | boolean;

export function getDBProviderConfig(
  providerType: AvailableDBProviderId,
  variables: GlobalVariable[],
): Record<string, DBProviderConfigValue> {
  if (providerType === "chroma_cloud") {
    return {
      mode: "cloud",
      tenant_variable: CHROMA_CLOUD_VARIABLES.TENANT,
      database_variable: CHROMA_CLOUD_VARIABLES.DATABASE,
      api_key_variable: CHROMA_CLOUD_VARIABLES.API_KEY,
      cloud_region:
        getGlobalVariableValue(variables, CHROMA_CLOUD_VARIABLES.REGION) ??
        "us-east-1",
    };
  }

  if (providerType !== "opensearch") {
    return {};
  }

  return {
    url_variable: OPENSEARCH_VARIABLES.URL,
    username_variable: OPENSEARCH_VARIABLES.USERNAME,
    password_variable: OPENSEARCH_VARIABLES.PASSWORD,
    index_name:
      getGlobalVariableValue(variables, OPENSEARCH_VARIABLES.INDEX_NAME) ?? "",
    vector_field:
      getGlobalVariableValue(variables, OPENSEARCH_VARIABLES.VECTOR_FIELD) ??
      "vector_field",
    text_field:
      getGlobalVariableValue(variables, OPENSEARCH_VARIABLES.TEXT_FIELD) ??
      "text",
    // Resolve booleans on the client so the backend always sees real
    // ``bool`` values; otherwise ``bool("false")`` evaluates to ``True``
    // in Python and silently flips the toggle.
    use_ssl: parseBooleanGlobalVariable(
      variables,
      OPENSEARCH_VARIABLES.USE_SSL,
      true,
    ),
    verify_certs: parseBooleanGlobalVariable(
      variables,
      OPENSEARCH_VARIABLES.VERIFY_CERTS,
      true,
    ),
  };
}

/**
 * Translate a frontend provider UI ID to the backend API ``backend_type``
 * string. ``"chroma_cloud"`` maps to ``"chroma"`` because the backend
 * disambiguates local vs. cloud via ``backend_config["mode"]``.
 */
export function toAPIBackendType(frontendId: AvailableDBProviderId): string {
  return frontendId === "chroma_cloud" ? "chroma" : frontendId;
}

/**
 * Re-hydrate a stored ``(backend_type, backend_config)`` pair from the
 * server into the frontend's UI provider ID. The DB always stores
 * ``backend_type = "chroma"`` for both local and cloud Chroma; the
 * ``mode`` key in ``backend_config`` is the discriminator.
 */
export function resolveUIBackendType(
  backendType: string | undefined,
  backendConfig: Record<string, unknown> | undefined,
): AvailableDBProviderId {
  if (backendType === "opensearch") return "opensearch";
  // Already a frontend UI ID — pass through directly.
  if (backendType === "chroma_cloud") return "chroma_cloud";
  // Server always stores "chroma" for both modes; mode discriminates.
  if (backendType === "chroma" && backendConfig?.["mode"] === "cloud")
    return "chroma_cloud";
  return "chroma";
}

export function isDBProviderConfigured(
  providerType: AvailableDBProviderId,
  variables: GlobalVariable[],
): boolean {
  if (providerType === "chroma") {
    return true;
  }

  const provider = getDBProviderOption(providerType);
  // Boolean fields always have a defined default, so they don't gate
  // "configured" status — only required text fields do.
  return provider.configFields
    .filter(
      (field): field is DBProviderTextField =>
        field.kind !== "boolean" && field.required,
    )
    .every((field) => {
      if (field.isSecret) {
        // Credential-type variables have their values masked (empty) in the
        // global-variables API response, so checking the value would always
        // return false even when the secret is saved. Check existence instead.
        return variables.some((v) => v.name === field.variableKey);
      }
      return Boolean(getGlobalVariableValue(variables, field.variableKey));
    });
}

export function getDefaultDBProviderConfig(variables: GlobalVariable[]): {
  backendType: AvailableDBProviderId;
  backendConfig: Record<string, DBProviderConfigValue>;
} {
  const backendType = getActiveDBProvider(variables);
  return {
    backendType,
    backendConfig: getDBProviderConfig(backendType, variables),
  };
}
