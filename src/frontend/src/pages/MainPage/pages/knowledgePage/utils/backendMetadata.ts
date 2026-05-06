import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";

/**
 * Display labels for the backends actually exposed in the UI.
 *
 * Stubbed backends (mongodb / astra / postgres) are intentionally
 * absent; if a legacy KB row carries one of those values the helper
 * falls back to the raw identifier so it's still visible.
 *
 * Note: the DB always stores ``backend_type = "chroma"`` for both local
 * and cloud Chroma. Pass ``backendConfig`` so the label can distinguish
 * them via ``backend_config["mode"]``.
 */
const BACKEND_LABELS: Record<string, string> = {
  chroma: "Chroma Local",
  opensearch: "OpenSearch",
};

export const getKnowledgeBaseBackendLabel = (
  backendType?: string,
  backendConfig?: Record<string, unknown>,
): string => {
  if (backendType === "chroma" && backendConfig?.["mode"] === "cloud") {
    return "Chroma Cloud";
  }
  const normalized = backendType || "chroma";
  return BACKEND_LABELS[normalized] || normalized;
};

export const getKnowledgeBaseBackendTarget = (
  knowledgeBase: Pick<KnowledgeBaseInfo, "backend_type" | "backend_config">,
): string | null => {
  const backendType = knowledgeBase.backend_type || "chroma";
  const backendConfig = knowledgeBase.backend_config || {};

  if (backendType === "chroma" && backendConfig["mode"] === "cloud") {
    const database = backendConfig["database"];
    return typeof database === "string" && database ? database : "Chroma Cloud";
  }

  if (backendType === "chroma") {
    return "Stored locally in Langflow";
  }

  if (backendType === "opensearch") {
    const indexName = backendConfig.index_name;
    if (typeof indexName === "string") {
      return indexName;
    }
  }

  return null;
};
