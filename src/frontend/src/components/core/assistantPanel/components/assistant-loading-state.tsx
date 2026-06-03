import { memo, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  ChevronRight,
  Code2,
  Loader2,
} from "lucide-react";
import type {
  AgenticProgressState,
  CompactFlowNode,
} from "@/controllers/API/queries/agentic";
import { cn } from "@/utils/utils";

interface AssistantLoadingStateProps {
  progress: AgenticProgressState;
  streamingContent?: string;
  onValidationComplete?: () => void;
}

const FLOW_STEPS = [
  "generating_flow",
  "extracting_flow",
  "validating_flow",
  "validated_flow",
] as const;

const FLOW_STEP_LABELS: Record<string, string> = {
  generating_flow: "Designing flow",
  extracting_flow: "Extracting structure",
  validating_flow: "Validating components",
  validated_flow: "Flow ready",
};

/** Animated row of node chips that reveals one node at a time. */
function FlowNodeTimeline({ nodes }: { nodes: CompactFlowNode[] }) {
  const [visibleCount, setVisibleCount] = useState(0);

  useEffect(() => {
    if (nodes.length === 0) return;
    setVisibleCount(0);
    let i = 0;
    const interval = setInterval(() => {
      i += 1;
      setVisibleCount(i);
      if (i >= nodes.length) clearInterval(interval);
    }, 220);
    return () => clearInterval(interval);
  }, [nodes]);

  return (
    <div className="flex flex-wrap items-center gap-1.5 py-1">
      {nodes.map((node, idx) => (
        <span key={node.id} className="flex items-center gap-1.5">
          <span
            className={cn(
              "rounded-md border px-2 py-0.5 text-xs font-medium transition-all duration-300",
              idx < visibleCount
                ? "border-violet-400/40 bg-violet-500/10 text-violet-300 opacity-100 translate-y-0"
                : "opacity-0 translate-y-1 pointer-events-none",
            )}
          >
            {node.type}
          </span>
          {idx < nodes.length - 1 && idx < visibleCount - 1 && (
            <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground/60" />
          )}
          {idx < nodes.length - 1 && idx >= visibleCount - 1 && (
            <span className="h-3 w-3" />
          )}
        </span>
      ))}
      {visibleCount < nodes.length && (
        <Loader2 className="h-3 w-3 animate-spin text-muted-foreground/50" />
      )}
    </div>
  );
}

/** Step-by-step progress track for flow generation. */
function FlowStepTrack({ currentStep }: { currentStep: string }) {
  const steps = FLOW_STEPS.filter((s) => s !== "validated_flow");
  const currentIdx = FLOW_STEPS.indexOf(currentStep as (typeof FLOW_STEPS)[number]);

  return (
    <div className="flex items-center gap-0">
      {steps.map((step, idx) => {
        const done = currentIdx > idx;
        const active = currentIdx === idx;
        return (
          <span key={step} className="flex items-center gap-0">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full transition-colors duration-300",
                done
                  ? "bg-violet-400"
                  : active
                    ? "bg-violet-400 animate-pulse"
                    : "bg-muted-foreground/30",
              )}
            />
            {idx < steps.length - 1 && (
              <span
                className={cn(
                  "h-px w-6 transition-colors duration-500",
                  done ? "bg-violet-400/60" : "bg-muted-foreground/20",
                )}
              />
            )}
          </span>
        );
      })}
    </div>
  );
}

function AssistantLoadingStateComponent({
  progress,
  streamingContent,
  onValidationComplete,
}: AssistantLoadingStateProps) {
  const [codeOpen, setCodeOpen] = useState(true);
  const streamingRef = useRef<HTMLPreElement>(null);

  const isValidated = progress.step === "validated";
  const isFlowValidated = progress.step === "validated_flow";
  const isFlowStep = FLOW_STEPS.includes(
    progress.step as (typeof FLOW_STEPS)[number],
  );
  const isReady = (isValidated && !!progress.componentCode) || isFlowValidated;
  const finalCode = progress.componentCode;
  const hasStreaming = !!streamingContent && streamingContent.length > 0;
  const showStreamingPreview = !finalCode && hasStreaming && !isFlowStep;

  const flowNodes = progress.flowData?.nodes ?? [];
  const flowEdgeCount = progress.flowData?.edges?.length ?? 0;

  // Auto-scroll streaming preview
  useEffect(() => {
    if (streamingRef.current) {
      streamingRef.current.scrollTop = streamingRef.current.scrollHeight;
    }
  }, [streamingContent]);

  return (
    <div className="w-full max-w-[500px] rounded-lg border border-border bg-background">
      {/* Header — status line */}
      <div className="flex items-center gap-2 px-4 py-3 text-sm font-medium">
        {isReady ? (
          <Check className="h-4 w-4 text-accent-emerald-foreground" />
        ) : (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        )}
        <span
          className={
            isReady ? "text-accent-emerald-foreground" : "text-foreground"
          }
        >
          {isFlowValidated
            ? "Flow ready"
            : isFlowStep
              ? (FLOW_STEP_LABELS[progress.step] ?? "Building flow...")
              : isReady
                ? "Component ready"
                : (progress.message ?? "Working...")}
        </span>

        {/* Step track dots for flow generation */}
        {isFlowStep && !isFlowValidated && (
          <span className="ml-auto">
            <FlowStepTrack currentStep={progress.step} />
          </span>
        )}

        {progress.className && !isFlowStep && (
          <span className="ml-auto rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {progress.className}
          </span>
        )}
      </div>

      <div
        className={cn(
          showStreamingPreview ||
            progress.error ||
            progress.attempt > 1 ||
            finalCode ||
            isReady ||
            (isFlowStep && flowNodes.length > 0)
            ? "px-4 pb-4"
            : "",
        )}
      >
        {/* ── Flow generation visual ── */}
        {isFlowStep && (
          <div className="space-y-3">
            {/* Node-by-node reveal once we have flow data */}
            {flowNodes.length > 0 ? (
              <div>
                <FlowNodeTimeline nodes={flowNodes} />
                {flowEdgeCount > 0 && (
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {flowNodes.length} nodes · {flowEdgeCount} edges
                  </p>
                )}
              </div>
            ) : (
              /* Skeleton shimmer while LLM is generating */
              <div className="flex items-center gap-1.5">
                {[48, 64, 56].map((w, i) => (
                  <span key={i} className="flex items-center gap-1.5">
                    <span
                      className="h-6 animate-pulse rounded-md bg-muted"
                      style={{ width: `${w}px`, animationDelay: `${i * 150}ms` }}
                    />
                    {i < 2 && (
                      <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground/30" />
                    )}
                  </span>
                ))}
                <span className="ml-1 text-xs text-muted-foreground/50">
                  generating...
                </span>
              </div>
            )}

            {/* Retry counter */}
            {progress.attempt > 1 && (
              <div className="text-xs text-muted-foreground">
                Attempt {progress.attempt} of {progress.maxAttempts}
              </div>
            )}

            {/* Validation error */}
            {progress.error && (
              <div className="w-fit rounded-md bg-destructive/5 px-3 py-2 text-xs text-destructive">
                {progress.error}
              </div>
            )}
          </div>
        )}

        {/* ── Component generation ── */}
        {!isFlowStep && (
          <>
            {/* Live streaming */}
            {showStreamingPreview && (
              <pre
                ref={streamingRef}
                className="max-h-[300px] overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed"
              >
                <code className="whitespace-pre-wrap">{streamingContent}</code>
              </pre>
            )}

            {/* Validation error */}
            {progress.error && (
              <div className="mt-2 w-fit rounded-md bg-destructive/5 px-3 py-2 text-xs text-destructive">
                {progress.error}
              </div>
            )}

            {/* Retry counter */}
            {progress.attempt > 1 && (
              <div className="mt-3 text-xs text-muted-foreground">
                Attempt {progress.attempt} of {progress.maxAttempts}
              </div>
            )}

            {/* Final extracted code */}
            {finalCode && (
              <div className="mt-3">
                <button
                  type="button"
                  onClick={() => setCodeOpen((prev) => !prev)}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                >
                  {codeOpen ? (
                    <ChevronDown className="h-3 w-3" />
                  ) : (
                    <ChevronRight className="h-3 w-3" />
                  )}
                  <Code2 className="h-3 w-3" />
                  <span>Code</span>
                </button>
                {codeOpen && (
                  <pre className="mt-2 max-h-[250px] overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed">
                    <code>{finalCode}</code>
                  </pre>
                )}
              </div>
            )}

            {/* Continue — user controls transition */}
            {isReady && (
              <button
                type="button"
                data-testid="assistant-continue-button"
                onClick={() => onValidationComplete?.()}
                className="mt-4 flex w-full items-center justify-center gap-2 rounded-md bg-accent-emerald-foreground/10 px-4 py-2.5 text-sm font-medium text-accent-emerald-foreground transition-colors hover:bg-accent-emerald-foreground/20"
              >
                <span>Continue</span>
                <ArrowRight className="h-4 w-4" />
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export const AssistantLoadingState = memo(AssistantLoadingStateComponent);
export default AssistantLoadingState;
