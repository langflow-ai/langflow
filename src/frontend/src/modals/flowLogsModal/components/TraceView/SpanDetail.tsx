import { Badge } from "@/components/ui/badge";
import IconComponent from "@/components/common/genericIconComponent";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { cn } from "@/utils/utils";
import type { Span, SpanType } from "./types";

interface SpanDetailProps {
  span: Span | null;
}

/**
 * Get display name for span type
 */
function getSpanTypeLabel(type: SpanType): string {
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
}

/**
 * Format a cost value as currency
 */
function formatCost(cost: number | undefined): string {
  if (cost === undefined || cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(6)}`;
  return `$${cost.toFixed(4)}`;
}

/**
 * Format latency in human-readable format
 */
function formatLatency(ms: number): string {
  if (ms === 0) return "Running...";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  return `${(ms / 60000).toFixed(2)}m`;
}

/**
 * Format JSON data for display
 */
function formatJsonData(data: Record<string, unknown>): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

/**
 * Detail panel showing full information about a selected span
 * Includes inputs, outputs, model info, tokens, and errors
 */
export function SpanDetail({ span }: SpanDetailProps) {
  if (!span) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <div className="text-center">
          <IconComponent name="MousePointer" className="mx-auto mb-2 h-8 w-8" />
          <p className="text-sm">Select a span to view details</p>
        </div>
      </div>
    );
  }

  const hasInputs = Object.keys(span.inputs).length > 0;
  const hasOutputs = Object.keys(span.outputs).length > 0;
  const hasTokenUsage = span.tokenUsage && span.tokenUsage.totalTokens > 0;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">{span.name}</h3>
          <Badge
            variant={
              span.status === "success"
                ? "successStatic"
                : span.status === "error"
                  ? "errorStatic"
                  : "secondaryStatic"
            }
            size="sm"
          >
            {span.status}
          </Badge>
        </div>
        <div className="mt-1 flex items-center gap-4 text-sm text-muted-foreground">
          <span>{getSpanTypeLabel(span.type)}</span>
          {span.modelName && (
            <>
              <span className="text-border">|</span>
              <span>{span.modelName}</span>
            </>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Error message (if present) */}
        {span.error && (
          <div className="mb-4 rounded-md border border-error-foreground/20 bg-error-background/50 p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-error-foreground">
              <IconComponent name="AlertCircle" className="h-4 w-4" />
              Error
            </div>
            <p className="mt-1 text-sm text-error-foreground/90">{span.error}</p>
          </div>
        )}

        {/* Metrics row */}
        <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <MetricCard
            label="Latency"
            value={formatLatency(span.latencyMs)}
            icon="Clock"
          />
          {hasTokenUsage && (
            <>
              <MetricCard
                label="Tokens"
                value={span.tokenUsage!.totalTokens.toLocaleString()}
                icon="Hash"
              />
              <MetricCard
                label="Prompt"
                value={span.tokenUsage!.promptTokens.toLocaleString()}
                icon="ArrowUp"
              />
              <MetricCard
                label="Completion"
                value={span.tokenUsage!.completionTokens.toLocaleString()}
                icon="ArrowDown"
              />
            </>
          )}
        </div>

        {/* Cost (if applicable) */}
        {hasTokenUsage && span.tokenUsage!.cost > 0 && (
          <div className="mb-4 flex items-center justify-between rounded-md bg-muted p-3">
            <span className="text-sm font-medium">Estimated Cost</span>
            <span className="text-sm font-semibold">
              {formatCost(span.tokenUsage!.cost)}
            </span>
          </div>
        )}

        {/* Inputs section */}
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

        {/* Outputs section */}
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
            <p className="text-sm">No additional details available</p>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Metric card component for displaying key stats
 */
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
    <div className="rounded-md border border-border bg-background p-2">
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        <IconComponent name={icon} className="h-3 w-3" />
        {label}
      </div>
      <div className="mt-0.5 text-sm font-semibold">{value}</div>
    </div>
  );
}

/**
 * Section header with icon
 */
function SectionHeader({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="flex items-center gap-2 text-sm font-medium">
      <IconComponent name={icon} className="h-4 w-4 text-muted-foreground" />
      {title}
    </div>
  );
}
