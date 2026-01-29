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

  return (
    <div className="space-y-3">
      {/* Error card */}
      <div className="rounded-lg border border-destructive/30 bg-destructive/5">
        {/* Header */}
        <div className="flex items-center gap-2 border-b border-destructive/20 px-4 py-3">
          <AlertTriangle className="h-4 w-4 text-destructive" />
          <span className="text-sm font-medium text-destructive">
            Component validation failed
          </span>
          {result.validationAttempts && (
            <span className="ml-auto text-xs text-muted-foreground">
              {result.validationAttempts} attempts
            </span>
          )}
        </div>

        {/* Error message */}
        <div className="p-4">
          <p className="text-sm text-muted-foreground">
            The generated component could not be validated after multiple attempts.
          </p>
          {result.validationError && (
            <div className="mt-3 rounded-md bg-muted/50 p-3">
              <p className="font-mono text-xs text-destructive">
                {result.validationError}
              </p>
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
              Try again
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
