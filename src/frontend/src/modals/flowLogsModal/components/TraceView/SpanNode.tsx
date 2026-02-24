import { Badge } from "@/components/ui/badge";
import IconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import type { Span, SpanType } from "./types";

interface SpanNodeProps {
  span: Span;
  depth: number;
  isExpanded: boolean;
  isSelected: boolean;
  onToggle: () => void;
  onSelect: () => void;
}

/**
 * Get the icon name for each span type
 */
function getSpanIcon(type: SpanType): string {
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
}

/**
 * Get the badge variant based on status
 */
function getStatusVariant(
  status: Span["status"],
): "successStatic" | "errorStatic" | "secondaryStatic" {
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
}

/**
 * Format latency in a human-readable way
 */
function formatLatency(ms: number): string {
  if (ms === 0) return "...";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Format token count with abbreviation for large numbers
 */
function formatTokens(tokens: number | undefined): string | null {
  if (!tokens) return null;
  if (tokens < 1000) return `${tokens} tok`;
  return `${(tokens / 1000).toFixed(1)}k tok`;
}

/**
 * Single span row in the trace tree
 * Shows icon, name, latency, token count, and status
 */
export function SpanNode({
  span,
  depth,
  isExpanded,
  isSelected,
  onToggle,
  onSelect,
}: SpanNodeProps) {
  const hasChildren = span.children.length > 0;
  const tokenStr = formatTokens(span.tokenUsage?.totalTokens);

  return (
    <div
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 transition-colors",
        "hover:bg-muted/50",
        isSelected && "bg-muted",
      )}
      style={{ paddingLeft: `${depth * 16 + 8}px` }}
      onClick={onSelect}
      role="treeitem"
      aria-selected={isSelected}
      aria-expanded={hasChildren ? isExpanded : undefined}
    >
      {/* Expand/collapse button */}
      <button
        className={cn(
          "flex h-4 w-4 items-center justify-center rounded-sm text-muted-foreground transition-colors",
          hasChildren && "hover:bg-muted-foreground/20",
          !hasChildren && "invisible",
        )}
        onClick={(e) => {
          e.stopPropagation();
          if (hasChildren) onToggle();
        }}
        tabIndex={-1}
        aria-hidden={!hasChildren}
      >
        <IconComponent
          name={isExpanded ? "ChevronDown" : "ChevronRight"}
          className="h-3 w-3"
        />
      </button>

      {/* Span type icon */}
      <div
        className={cn(
          "flex h-5 w-5 items-center justify-center rounded",
          span.status === "error" && "text-error-foreground",
          span.status === "success" && "text-foreground",
          span.status === "running" && "text-muted-foreground",
        )}
      >
        <IconComponent name={getSpanIcon(span.type)} className="h-4 w-4" />
      </div>

      {/* Span name */}
      <span
        className={cn(
          "flex-1 truncate text-sm font-medium",
          span.status === "error" && "text-error-foreground",
        )}
      >
        {span.name}
      </span>

      {/* Token count (if applicable) */}
      {tokenStr && (
        <span className="text-xs text-muted-foreground">{tokenStr}</span>
      )}

      {/* Latency */}
      <span className="min-w-[48px] text-right text-xs text-muted-foreground">
        {formatLatency(span.latencyMs)}
      </span>

      {/* Status badge */}
      <Badge
        variant={getStatusVariant(span.status)}
        size="xq"
        className="min-w-[16px]"
      >
        {span.status === "running" ? (
          <IconComponent name="Loader2" className="h-3 w-3 animate-spin" />
        ) : span.status === "success" ? (
          <IconComponent name="Check" className="h-3 w-3" />
        ) : (
          <IconComponent name="X" className="h-3 w-3" />
        )}
      </Badge>
    </div>
  );
}
