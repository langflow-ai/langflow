import type { Span, SpanType } from "./types";

export const getSpanIcon = (type: SpanType): string => {
  const iconMap: Record<SpanType, string> = {
    agent: "Bot",
    chain: "Link",
    llm: "MessageSquare",
    tool: "Wrench",
    retriever: "Search",
    embedding: "Hash",
    parser: "FileText",
  };
  return iconMap[type] || "Circle";
};

export const getStatusVariant = (
  status: Span["status"],
): "successStatic" | "errorStatic" | "secondaryStatic" => {
  switch (status) {
    case "success":
      return "successStatic";
    case "error":
      return "errorStatic";
    case "running":
      return "secondaryStatic";
    default:
      return "secondaryStatic";
  }
};

export const formatSpanNodeLatency = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
};

export const formatTokens = (tokens: number | undefined): string | null => {
  if (!tokens) return null;
  if (tokens < 1000) return `${tokens}`;
  return `${(tokens / 1000).toFixed(1)}k`;
};

export const getSpanTypeLabel = (type: SpanType): string => {
  const labelMap: Record<SpanType, string> = {
    agent: "Agent",
    chain: "Chain",
    llm: "LLM",
    tool: "Tool",
    retriever: "Retriever",
    embedding: "Embedding",
    parser: "Parser",
  };
  return labelMap[type] || type;
};

export const formatCost = (cost: number | undefined): string => {
  if (cost === undefined || cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(6)}`;
  return `$${cost.toFixed(4)}`;
};

export const formatSpanDetailLatency = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  return `${(ms / 60000).toFixed(2)}m`;
};

export const formatJsonData = (data: Record<string, unknown>): string => {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
};
