import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, Code2 } from "lucide-react";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { Button } from "@/components/ui/button";
import type { AgenticResult } from "@/controllers/API/queries/agentic";

interface AssistantValidationFailedProps {
  result: AgenticResult;
  onRetry?: () => void;
}

export function AssistantValidationFailed({
  result,
  onRetry,
}: AssistantValidationFailedProps) {
  const [showCode, setShowCode] = useState(false);
  const [showErrorDetails, setShowErrorDetails] = useState(false);

  return (
    <div className="max-w-[80%] space-y-3">
      {/* Error card */}
      <div className="rounded-lg border border-destructive/30 bg-destructive/5">
        {/* Header */}
        <div className="flex items-center gap-2 border-b border-destructive/20 px-4 py-3">
          <AlertTriangle className="h-4 w-4 text-destructive" />
          <span className="text-sm font-medium text-destructive">
            Component generation failed
          </span>
        </div>

        {/* Friendly message */}
        <div className="p-4">
          <p className="text-sm text-foreground">
            The selected model was unable to generate valid component code. Try
            again or use a more capable model.
          </p>

          {/* Collapsible error details */}
          {result.validationError && (
            <div className="mt-3">
              <button
                type="button"
                onClick={() => setShowErrorDetails(!showErrorDetails)}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                {showErrorDetails ? (
                  <ChevronUp className="h-3 w-3" />
                ) : (
                  <ChevronDown className="h-3 w-3" />
                )}
                Error details
              </button>
              {showErrorDetails && (
                <div className="mt-2 max-h-[200px] overflow-auto rounded-md bg-muted/50 p-3">
                  <p className="whitespace-pre-wrap break-all font-mono text-xs text-destructive">
                    {result.validationError}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 border-t border-destructive/20 px-4 py-3">
          {result.componentCode && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowCode(!showCode)}
              className="h-8 gap-2 text-muted-foreground"
            >
              <Code2 className="h-3.5 w-3.5" />
              {showCode ? "Hide code" : "View code"}
              {showCode ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </Button>
          )}
          {onRetry && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRetry}
              className="ml-auto h-8"
            >
              Try Again
            </Button>
          )}
        </div>
      </div>

      {/* Code viewer */}
      {showCode && result.componentCode && (
        <SimplifiedCodeTabComponent
          language="python"
          code={result.componentCode}
          maxHeight="300px"
        />
      )}
    </div>
  );
}
