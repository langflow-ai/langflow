import { memo, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  ChevronRight,
  Code2,
  Loader2,
} from "lucide-react";
import type { AgenticProgressState } from "@/controllers/API/queries/agentic";

interface AssistantLoadingStateProps {
  progress: AgenticProgressState;
  streamingContent?: string;
  onValidationComplete?: () => void;
}

function AssistantLoadingStateComponent({
  progress,
  streamingContent,
  onValidationComplete,
}: AssistantLoadingStateProps) {
  const [codeOpen, setCodeOpen] = useState(true);
  const streamingRef = useRef<HTMLPreElement>(null);

  const isValidated = progress.step === "validated";
  const isReady = isValidated && !!progress.componentCode;
  const finalCode = progress.componentCode;
  const hasStreaming = !!streamingContent && streamingContent.length > 0;
  const showStreamingPreview = !finalCode && hasStreaming;

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
          {isReady ? "Component ready" : progress.message || "Working..."}
        </span>
        {progress.className && (
          <span className="ml-auto rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {progress.className}
          </span>
        )}
      </div>

      <div
        className={
          showStreamingPreview ||
          progress.error ||
          progress.attempt > 0 ||
          finalCode ||
          isReady
            ? "px-4 pb-4"
            : ""
        }
      >
        {/* Live streaming — the main content while LLM generates */}
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

        {/* Final extracted code — replaces streaming preview */}
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
      </div>
    </div>
  );
}

export const AssistantLoadingState = memo(AssistantLoadingStateComponent);
export default AssistantLoadingState;
