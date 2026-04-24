import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";

const BACKEND_LABELS: Record<string, string> = {
  chroma: "Chroma (local)",
  mongodb: "MongoDB Atlas",
  astra: "Astra DB",
  postgres: "Postgres (pgvector)",
  opensearch: "OpenSearch",
};

export const getKnowledgeBaseBackendLabel = (backendType?: string): string => {
  const normalized = backendType || "chroma";
  return BACKEND_LABELS[normalized] || normalized;
};

export const getKnowledgeBaseBackendTarget = (
  knowledgeBase: Pick<KnowledgeBaseInfo, "backend_type" | "backend_config">,
): string | null => {
  const backendType = knowledgeBase.backend_type || "chroma";
  const backendConfig = knowledgeBase.backend_config || {};

  if (backendType === "chroma") {
    return "Stored locally in Langflow";
  }

  if (backendType === "mongodb") {
    const database = backendConfig.database;
    const collection = backendConfig.collection;
    if (typeof database === "string" && typeof collection === "string") {
      return `${database}.${collection}`;
    }
    if (typeof collection === "string") {
      return collection;
    }
  }

  if (backendType === "astra") {
    const namespace = backendConfig.namespace;
    const collectionName = backendConfig.collection_name;
    if (
      typeof namespace === "string" &&
      namespace &&
      typeof collectionName === "string"
    ) {
      return `${namespace}.${collectionName}`;
    }
    if (typeof collectionName === "string") {
      return collectionName;
    }
  }

  if (backendType === "postgres") {
    const collectionName = backendConfig.collection_name;
    if (typeof collectionName === "string") {
      return collectionName;
    }
  }

  if (backendType === "opensearch") {
    const indexName = backendConfig.index_name;
    if (typeof indexName === "string") {
      return indexName;
    }
  }

  return null;
};
