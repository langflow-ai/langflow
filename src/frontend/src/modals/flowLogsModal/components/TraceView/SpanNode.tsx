import { useMemo } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { useTypesStore } from "@/stores/typesStore";
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

function getSpanTypeIcon(type: SpanType): string {
  const iconMap: Record<SpanType, string> = {
    run: "Workflow",
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

function useComponentIconMap(): Record<string, string> {
  const data = useTypesStore((state) => state.data);
  return useMemo(() => {
    const map: Record<string, string> = {};
    for (const category of Object.values(data)) {
      for (const component of Object.values(category)) {
        if (component.display_name && component.icon) {
          map[component.display_name] = component.icon;
        }
      }
    }
    return map;
  }, [data]);
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTokens(tokens: number | undefined): string | null {
  if (!tokens) return null;
  if (tokens < 1000) return `${tokens}`;
  return `${(tokens / 1000).toFixed(1)}k`;
}

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
  const iconMap = useComponentIconMap();
  const iconName = iconMap[span.name] || getSpanTypeIcon(span.type);

  return (
    <div
      className={cn(
        "group flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1.5 transition-colors",
        "hover:bg-muted/60",
        isSelected && "bg-muted",
      )}
      style={{ paddingLeft: `${depth * 16 + 8}px` }}
      onClick={onSelect}
      role="treeitem"
      aria-selected={isSelected}
      aria-expanded={hasChildren ? isExpanded : undefined}
    >
      {/* Expand/collapse */}
      <button
        className={cn(
          "flex h-4 w-4 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors",
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

      {/* Span icon */}
      <div
        className={cn(
          "flex h-5 w-5 shrink-0 items-center justify-center rounded",
          span.status === "error" && "text-destructive",
          span.status === "success" && "text-muted-foreground",
          span.status === "running" && "text-muted-foreground",
        )}
      >
        <IconComponent name={iconName} className="h-3.5 w-3.5" />
      </div>

      {/* Name */}
      <span
        className={cn(
          "flex-1 truncate text-xs",
          isSelected ? "font-medium" : "font-normal",
          span.status === "error" && "text-destructive",
        )}
      >
        {span.name}
      </span>

      {/* Tokens */}
      {tokenStr && (
        <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
          <IconComponent name="Coins" className="h-3 w-3" />
          {tokenStr}
        </span>
      )}

      {/* Latency */}
      <span className="min-w-[40px] shrink-0 text-right text-xs text-muted-foreground">
        {formatLatency(span.latencyMs)}
      </span>

      {/* Status icon */}
      <IconComponent
        name={
          span.status === "running"
            ? "Loader2"
            : span.status === "success"
              ? "CheckCircle2"
              : "XCircle"
        }
        className={cn(
          "h-3.5 w-3.5 shrink-0",
          span.status === "success" && "text-emerald-500",
          span.status === "error" && "text-destructive",
          span.status === "running" && "animate-spin text-muted-foreground",
        )}
      />
    </div>
  );
}
