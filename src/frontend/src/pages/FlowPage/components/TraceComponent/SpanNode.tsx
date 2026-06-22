import IconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import { SpanNodeProps } from "./types";
import { useSpanNode } from "./useSpanNode";

export function SpanNode({
  span,
  depth,
  isExpanded,
  isSelected,
  tabIndex,
  posInSet,
  setSize,
  onToggle,
  onSelect,
}: SpanNodeProps) {
  const {
    indentStyle,
    spanIconName,
    hasChildren,
    tokenStr,
    latency,
    ariaLabel,
    colorClass,
    iconName,
    shouldSpin,
    expandButtonLabel,
    handleKeyDown,
    handleExpandClick,
  } = useSpanNode({ span, depth, isExpanded, onSelect, onToggle });

  return (
    <div
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 transition-colors",
        "hover:bg-muted/50",
        isSelected && "bg-muted",
      )}
      style={indentStyle}
      onClick={onSelect}
      onKeyDown={handleKeyDown}
      data-testid={`span-node-${span.id}`}
      role="treeitem"
      aria-label={ariaLabel}
      aria-selected={isSelected}
      aria-expanded={hasChildren ? isExpanded : undefined}
      aria-posinset={posInSet}
      aria-setsize={setSize}
      tabIndex={tabIndex}
    >
      {/* Expand/collapse button */}
      <button
        className={cn(
          "flex h-4 w-4 items-center justify-center rounded-sm text-muted-foreground transition-colors",
          hasChildren && "hover:bg-muted-foreground/20",
          !hasChildren && "invisible",
        )}
        onClick={handleExpandClick}
        tabIndex={-1}
        aria-hidden={!hasChildren}
        aria-label={expandButtonLabel}
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
        <span className={cn(
          "flex items-center gap-0.5 text-xs",
          isSelected ? "text-foreground/65" : "text-muted-foreground",
        )}>
          <IconComponent name="Coins" className="h-3 w-3" />
          {tokenStr}
        </span>
      )}

      {/* Latency */}
      <span className={cn(
        "min-w-[48px] text-right text-xs",
        isSelected ? "text-foreground/65" : "text-muted-foreground",
      )}>
        {latency}
      </span>

      {/* Status icon */}
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
