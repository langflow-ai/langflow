import type { GlobalVariable } from "@/types/global_variables";

export const ACTIVE_KNOWLEDGE_BACKEND_VARIABLE = "LANGFLOW_KNOWLEDGE_BACKEND";

export const OPENSEARCH_VARIABLES = {
  URL: "OPENSEARCH_URL",
  USERNAME: "OPENSEARCH_USERNAME",
  PASSWORD: "OPENSEARCH_PASSWORD", // pragma: allowlist secret
  INDEX_NAME: "OPENSEARCH_INDEX_NAME",
  VECTOR_FIELD: "OPENSEARCH_VECTOR_FIELD",
  TEXT_FIELD: "OPENSEARCH_TEXT_FIELD",
} as const;

export type KnowledgeBackendId =
  | "chroma"
  | "opensearch"
  | "astra"
  | "mongodb"
  | "postgres";

export interface KnowledgeBackendConfigField {
  label: string;
  variableKey: string;
  required: boolean;
  isSecret: boolean;
  placeholder: string;
  defaultValue?: string;
}

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
  KNOWLEDGE_BACKEND_OPTIONS.filter((backend) => backend.status === "available");

export function getGlobalVariableValue(
  variables: GlobalVariable[],
  name: string,
): string | undefined {
  const value = variables.find((variable) => variable.name === name)?.value;
  return typeof value === "string" && value.trim() ? value : undefined;
}

export function getActiveKnowledgeBackend(
  variables: GlobalVariable[],
): "chroma" | "opensearch" {
  const configuredBackend = getGlobalVariableValue(
    variables,
    ACTIVE_KNOWLEDGE_BACKEND_VARIABLE,
  );
  return configuredBackend === "opensearch" ? "opensearch" : "chroma";
}

export function getDefaultKnowledgeBackendConfig(variables: GlobalVariable[]): {
  backendType: "chroma" | "opensearch";
  backendConfig: Record<string, string>;
} {
  const backendType = getActiveKnowledgeBackend(variables);
  if (backendType !== "opensearch") {
    return { backendType: "chroma", backendConfig: {} };
  }

  return {
    backendType,
    backendConfig: {
      url_variable: OPENSEARCH_VARIABLES.URL,
      username_variable: OPENSEARCH_VARIABLES.USERNAME,
      password_variable: OPENSEARCH_VARIABLES.PASSWORD,
      index_name:
        getGlobalVariableValue(variables, OPENSEARCH_VARIABLES.INDEX_NAME) ??
        "",
      vector_field:
        getGlobalVariableValue(variables, OPENSEARCH_VARIABLES.VECTOR_FIELD) ??
        "vector_field",
      text_field:
        getGlobalVariableValue(variables, OPENSEARCH_VARIABLES.TEXT_FIELD) ??
        "text",
    },
  };
}
