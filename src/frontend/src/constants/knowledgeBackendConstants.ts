import type { GlobalVariable } from "@/types/global_variables";

export const ACTIVE_KNOWLEDGE_BACKEND_VARIABLE = "LANGFLOW_KNOWLEDGE_BACKEND";

export const OPENSEARCH_VARIABLES = {
  URL: "OPENSEARCH_URL",
  USERNAME: "OPENSEARCH_USERNAME",
  PASSWORD: "OPENSEARCH_PASSWORD", // pragma: allowlist secret
  INDEX_NAME: "OPENSEARCH_INDEX_NAME",
  VECTOR_FIELD: "OPENSEARCH_VECTOR_FIELD",
  TEXT_FIELD: "OPENSEARCH_TEXT_FIELD",
  // Boolean toggles for TLS connection behavior. Persisted as
  // "true"/"false" strings via the global-variable pipeline and
  // coerced back to booleans inside ``getKnowledgeBackendConfig``.
  USE_SSL: "OPENSEARCH_USE_SSL",
  VERIFY_CERTS: "OPENSEARCH_VERIFY_CERTS",
} as const;

export type KnowledgeBackendId =
  | "chroma"
  | "opensearch"
  | "astra"
  | "mongodb"
  | "postgres";

export type AvailableKnowledgeBackendId = Extract<
  KnowledgeBackendId,
  "chroma" | "opensearch"
>;

export interface KnowledgeBackendTextField {
  kind?: "text";
  label: string;
  variableKey: string;
  required: boolean;
  isSecret: boolean;
  placeholder: string;
  defaultValue?: string;
}

export interface KnowledgeBackendBooleanField {
  kind: "boolean";
  label: string;
  variableKey: string;
  helperText?: string;
  defaultValue: boolean;
}

export type KnowledgeBackendConfigField =
  | KnowledgeBackendTextField
  | KnowledgeBackendBooleanField;

export interface KnowledgeBackendOption {
  id: KnowledgeBackendId;
  label: string;
  description: string;
  icon: string;
  status: "available" | "coming_soon";
  defaultEnabled?: boolean;
  configFields: KnowledgeBackendConfigField[];
}

export const KNOWLEDGE_BACKEND_OPTIONS: KnowledgeBackendOption[] = [
  {
    id: "chroma",
    label: "Chroma",
    description:
      "Local vector storage bundled with Langflow. No additional configuration required.",
    icon: "Chroma",
    status: "available",
    defaultEnabled: true,
    configFields: [],
  },
  {
    id: "opensearch",
    label: "OpenSearch",
    description:
      "External OpenSearch k-NN index for self-hosted or managed clusters.",
    icon: "Search",
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
        label: "Username",
        variableKey: OPENSEARCH_VARIABLES.USERNAME,
        required: false,
        isSecret: false,
        placeholder: "admin",
      },
      {
        label: "Password",
        variableKey: OPENSEARCH_VARIABLES.PASSWORD,
        required: false,
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
    icon: "Database",
    status: "coming_soon",
    configFields: [],
  },
  {
    id: "postgres",
    label: "Postgres pgvector",
    description: "Postgres-backed vector storage.",
    icon: "Database",
    status: "coming_soon",
    configFields: [],
  },
];

export const AVAILABLE_KNOWLEDGE_BACKEND_OPTIONS =
  KNOWLEDGE_BACKEND_OPTIONS.filter(
    (
      backend,
    ): backend is KnowledgeBackendOption & {
      id: AvailableKnowledgeBackendId;
    } => backend.status === "available",
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

export function getActiveKnowledgeBackend(
  variables: GlobalVariable[],
): AvailableKnowledgeBackendId {
  const configuredBackend = getGlobalVariableValue(
    variables,
    ACTIVE_KNOWLEDGE_BACKEND_VARIABLE,
  );
  return configuredBackend === "opensearch" ? "opensearch" : "chroma";
}

export function getKnowledgeBackendOption(
  backendId: KnowledgeBackendId | string | undefined,
): KnowledgeBackendOption {
  return (
    KNOWLEDGE_BACKEND_OPTIONS.find((backend) => backend.id === backendId) ??
    KNOWLEDGE_BACKEND_OPTIONS[0]
  );
}

export type KnowledgeBackendConfigValue = string | boolean;

export function getKnowledgeBackendConfig(
  backendType: AvailableKnowledgeBackendId,
  variables: GlobalVariable[],
): Record<string, KnowledgeBackendConfigValue> {
  if (backendType !== "opensearch") {
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

export function isKnowledgeBackendConfigured(
  backendType: AvailableKnowledgeBackendId,
  variables: GlobalVariable[],
): boolean {
  if (backendType === "chroma") {
    return true;
  }

  const backend = getKnowledgeBackendOption(backendType);
  // Boolean fields always have a defined default, so they don't gate
  // "configured" status — only required text fields do.
  return backend.configFields
    .filter(
      (field): field is KnowledgeBackendTextField =>
        field.kind !== "boolean" && field.required,
    )
    .every((field) =>
      Boolean(getGlobalVariableValue(variables, field.variableKey)),
    );
}

export function getDefaultKnowledgeBackendConfig(variables: GlobalVariable[]): {
  backendType: AvailableKnowledgeBackendId;
  backendConfig: Record<string, KnowledgeBackendConfigValue>;
} {
  const backendType = getActiveKnowledgeBackend(variables);
  return {
    backendType,
    backendConfig: getKnowledgeBackendConfig(backendType, variables),
  };
}
