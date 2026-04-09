import { useCallback, useEffect, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Loading } from "@/components/ui/loading";
import { useGetTraceQuery } from "@/controllers/API/queries/traces";
import { parseSpanStatus } from "@/controllers/API/queries/traces/helpers";
import { formatSmartTimestamp } from "@/utils/dateTime";
import { cn } from "@/utils/utils";
import { SpanDetail } from "./SpanDetail";
import { SpanTree } from "./SpanTree";
import {
  formatCost,
  formatIOPreview,
  formatTotalLatency,
  getStatusVariant,
} from "./traceViewHelpers";
import { Span, TraceAccordionItemProps } from "./types";

export function TraceAccordionItem({
  traceId,
  traceName,
  traceStatus,
  traceStartTime,
  totalLatencyMs,
  totalTokens,
  totalCost,
  sessionId,
  input,
  output,
  isExpanded,
  onTraceClick,
}: TraceAccordionItemProps) {
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);

  // Only fetch full trace details (with spans) when expanded
  const { data: trace, isLoading } = useGetTraceQuery(
    { traceId },
    { enabled: isExpanded },
  );

  // Set initial selected span when trace loads
  useEffect(() => {
    if (trace?.spans && trace.spans.length > 0 && !selectedSpan) {
      setSelectedSpan(trace.spans[0]);
    }
  }, [trace?.spans, selectedSpan]);

  const handleSelectSpan = useCallback((span: Span) => {
    setSelectedSpan(span);
  }, []);

  return (
    <AccordionItem
      value={traceId}
      className={cn(
        "border-b border-border",
        traceStatus === "error" && "bg-error/5",
      )}
    >
      <AccordionTrigger
        className={cn(
          "px-4 py-3 hover:bg-muted/50",
          traceStatus === "error" && "hover:bg-error/10",
        )}
        onClick={(e) => {
          if (!onTraceClick) return;
          e.preventDefault();
          e.stopPropagation();
          onTraceClick(traceId);
        }}
        onKeyDown={(e) => {
          if (!onTraceClick) return;
          if (e.key !== "Enter" && e.key !== " ") return;
          e.preventDefault();
          e.stopPropagation();
          onTraceClick(traceId);
        }}
      >
        <div className="flex w-full items-center justify-between pr-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <IconComponent
                name="Activity"
                className="h-4 w-4 text-muted-foreground"
              />
              <span className="text-sm font-medium">{traceName}</span>
            </div>
            <Badge
              variant={getStatusVariant(parseSpanStatus(traceStatus))}
              size="sm"
            >
              {traceStatus}
            </Badge>
            <Badge variant="outline" size="sm" className="font-mono text-xs">
              <IconComponent name="Hash" className="mr-1 h-3 w-3" />
              {sessionId}
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <IconComponent name="Calendar" className="h-3 w-3" />
              {formatSmartTimestamp(traceStartTime)}
            </span>
            <span className="flex items-center gap-1">
              <IconComponent name="Clock" className="h-3 w-3" />
              {formatTotalLatency(totalLatencyMs)}
            </span>
            {totalTokens > 0 && (
              <span className="flex items-center gap-1">
                <IconComponent name="Coins" className="h-3 w-3" />
                {totalTokens.toLocaleString()} tokens
              </span>
            )}
            {totalCost > 0 && (
              <span className="flex items-center gap-1">
                <IconComponent name="DollarSign" className="h-3 w-3" />
                {formatCost(totalCost)}
              </span>
            )}
          </div>
        </div>
        {/* Input/Output Preview Row */}
        {(input || output) && (
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            {input && (
              <div className="flex flex-col gap-1">
                <span className="font-medium text-muted-foreground">
                  Input:
                </span>
                <span className="truncate text-foreground/80">
                  {formatIOPreview(input)}
                </span>
              </div>
            )}
            {output && (
              <div className="flex flex-col gap-1">
                <span className="font-medium text-muted-foreground">
                  Output:
                </span>
                <span className="truncate text-foreground/80">
                  {formatIOPreview(output)}
                </span>
              </div>
            )}
          </div>
        )}
      </AccordionTrigger>
      <AccordionContent className="px-0 pb-0">
        {isLoading ? (
          <div className="flex h-[500px] items-center justify-center">
            <Loading size={24} className="text-primary" />
          </div>
        ) : trace ? (
          <div className="flex h-[500px] overflow-hidden border-t border-border">
            {/* Left panel: Span tree */}
            <div className="w-1/3 min-w-[280px] overflow-y-auto border-r border-border p-2">
              <SpanTree
                spans={trace.spans ?? []}
                selectedSpanId={selectedSpan?.id ?? null}
                onSelectSpan={handleSelectSpan}
              />
            </div>

            {/* Right panel: Span details */}
            <div className="flex-1 overflow-hidden">
              <SpanDetail span={selectedSpan} />
            </div>
          </div>
        ) : (
          <div className="flex h-[500px] items-center justify-center text-sm text-muted-foreground">
            Failed to load trace details
          </div>
        )}
      </AccordionContent>
    </AccordionItem>
  );
}
