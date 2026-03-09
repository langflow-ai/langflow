import { useMemo } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import {
  formatTokens,
  formatTotalLatency,
  getSpanIcon,
  getStatusIconProps,
} from "./traceViewHelpers";
import { SpanNodeProps } from "./types";

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
  const nodes = useFlowStore((state) => state.nodes);
  const componentIconMap = useMemo(() => {
    const map = new Map<string, string>();
    nodes.forEach((node) => {
      const nodeData = node.data?.node;
      const displayName = nodeData?.display_name;
      const icon = nodeData && "icon" in nodeData ? nodeData.icon : undefined;
      if (displayName && icon) {
        map.set(displayName.toLowerCase(), icon);
      }
    });
    return map;
  }, [nodes]);

  const spanIconName = span.name
    ? (componentIconMap.get(span.name.toLowerCase()) ?? getSpanIcon(span.type))
    : getSpanIcon(span.type);
  const hasChildren = span.children.length > 0;
  const tokenStr = formatTokens(span.tokenUsage?.totalTokens);

  const { colorClass, iconName, shouldSpin } = getStatusIconProps(span.status);

  return (
    <div
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 transition-colors",
        "hover:bg-muted/50",
        isSelected && "bg-muted",
      )}
      style={{ paddingLeft: `${depth * 16 + 8}px` }}
      onClick={onSelect}
      data-testid={`span-node-${span.id}`}
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
          span.status === "ok" && "text-foreground",
          span.status === "unset" && "text-muted-foreground",
        )}
      >
        <IconComponent name={spanIconName} className="h-4 w-4" />
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
        <span className="flex items-center gap-0.5 text-xs text-muted-foreground">
          <IconComponent name="Coins" className="h-3 w-3" />
          {tokenStr}
        </span>
      )}

      {/* Latency */}
      <span className="min-w-[48px] text-right text-xs text-muted-foreground">
        {formatTotalLatency(span.latencyMs)}
      </span>

      {/* Status badge */}

      <IconComponent
        name={iconName}
        className={`h-4 w-4 ${colorClass} ${shouldSpin ? "animate-spin" : ""}`}
        aria-label={span.status}
        dataTestId={`flow-log-status-${span.status}`}
        skipFallback
      />
    </div>
  );
}
