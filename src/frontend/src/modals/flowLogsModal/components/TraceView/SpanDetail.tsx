import IconComponent from "@/components/common/genericIconComponent";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { cn } from "@/utils/utils";
import type { Span, SpanType } from "./types";

interface SpanDetailProps {
  span: Span | null;
}

function getSpanTypeLabel(type: SpanType): string {
  const labelMap: Record<SpanType, string> = {
    run: "Run",
    agent: "Agent",
    chain: "Chain",
    llm: "LLM",
    tool: "Tool",
    retriever: "Retriever",
    embedding: "Embedding",
    parser: "Parser",
  };
  return labelMap[type] || type;
}

function formatCost(cost: number | undefined): string {
  if (cost === undefined || cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(6)}`;
  return `$${cost.toFixed(4)}`;
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  return `${(ms / 60000).toFixed(2)}m`;
}

function formatJsonData(data: Record<string, unknown>): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

export function SpanDetail({ span }: SpanDetailProps) {
  if (!span) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <div className="text-center">
          <IconComponent name="MousePointer" className="mx-auto mb-2 h-6 w-6 opacity-40" />
          <p className="text-xs">Select a span to view details</p>
        </div>
      </div>
    );
  }

  const hasInputs = Object.keys(span.inputs).length > 0;
  const hasOutputs = Object.keys(span.outputs).length > 0;
  const hasTokenUsage = span.tokenUsage && span.tokenUsage.totalTokens > 0;
  const showTokens = span.type === "llm" || span.type === "run";

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-border bg-background px-4 py-2.5">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold">{span.name}</h3>
          <div
            className={cn(
              "flex items-center gap-1 rounded-full px-2 py-0.5 text-xs",
              span.status === "success" && "bg-emerald-500/10 text-emerald-500",
              span.status === "error" && "bg-destructive/10 text-destructive",
              span.status === "running" && "bg-muted text-muted-foreground",
            )}
          >
            <IconComponent
              name={
                span.status === "success"
                  ? "CheckCircle2"
                  : span.status === "error"
                    ? "XCircle"
                    : "Loader2"
              }
              className={cn(
                "h-3 w-3",
                span.status === "running" && "animate-spin",
              )}
            />
            {span.status}
          </div>
        </div>
        <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
          <span>{getSpanTypeLabel(span.type)}</span>
          {span.modelName && (
            <>
              <span className="text-border">|</span>
              <span className="font-mono">{span.modelName}</span>
            </>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Error message */}
        {span.error && (
          <div className="mb-4 rounded-md border border-destructive/20 bg-destructive/5 p-3">
            <div className="flex items-center gap-2 text-xs font-medium text-destructive">
              <IconComponent name="AlertCircle" className="h-3.5 w-3.5" />
              Error
            </div>
            <p className="mt-1 text-xs text-destructive/90">{span.error}</p>
          </div>
        )}

        {/* Metrics row */}
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricCard
            label="Latency"
            value={formatLatency(span.latencyMs)}
            icon="Clock"
          />
          {(hasTokenUsage || showTokens) && (
            <>
              <MetricCard
                label="Tokens"
                value={hasTokenUsage ? span.tokenUsage!.totalTokens.toLocaleString() : "\u2014"}
                icon="Coins"
              />
              <MetricCard
                label="Prompt"
                value={hasTokenUsage ? span.tokenUsage!.promptTokens.toLocaleString() : "\u2014"}
                icon="ArrowUp"
              />
              <MetricCard
                label="Completion"
                value={hasTokenUsage ? span.tokenUsage!.completionTokens.toLocaleString() : "\u2014"}
                icon="ArrowDown"
              />
            </>
          )}
        </div>

        {/* Cost */}
        {hasTokenUsage && span.tokenUsage!.cost > 0 && (
          <div className="mb-4 flex items-center justify-between rounded-md bg-muted/40 px-3 py-2">
            <span className="text-xs font-medium">Estimated Cost</span>
            <span className="font-mono text-xs font-semibold">
              {formatCost(span.tokenUsage!.cost)}
            </span>
          </div>
        )}

        {/* Inputs */}
        {hasInputs && (
          <div className="mb-4">
            <SectionHeader icon="ArrowRight" title="Input" />
            <div className="mt-2">
              <SimplifiedCodeTabComponent
                language="json"
                code={formatJsonData(span.inputs)}
              />
            </div>
          </div>
        )}

        {/* Outputs */}
        {hasOutputs && (
          <div className="mb-4">
            <SectionHeader icon="ArrowLeft" title="Output" />
            <div className="mt-2">
              <SimplifiedCodeTabComponent
                language="json"
                code={formatJsonData(span.outputs)}
              />
            </div>
          </div>
        )}

        {/* Empty state */}
        {!hasInputs && !hasOutputs && !span.error && (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <p className="text-xs">No additional details available</p>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: string;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-2">
      <div className="flex items-center gap-1 text-xs text-muted-foreground/70">
        <IconComponent name={icon} className="h-3 w-3" />
        {label}
      </div>
      <div className="mt-0.5 font-mono text-xs font-semibold">{value}</div>
    </div>
  );
}

function SectionHeader({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="flex items-center gap-2 text-xs font-medium">
      <IconComponent name={icon} className="h-3.5 w-3.5 text-muted-foreground" />
      {title}
    </div>
  );
}
