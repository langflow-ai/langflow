import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { cn } from "@/utils/utils";

type FailedComponentLineProps = {
  componentName?: string;
  code?: string;
  error?: string;
};

export const FailedComponentLine = ({
  componentName,
  code,
  error,
}: FailedComponentLineProps) => {
  const [isCodeExpanded, setIsCodeExpanded] = useState(false);
  const displayName = componentName || "Component";

  return (
    <div className="flex flex-col gap-1 py-1">
      <div className="flex items-center gap-2">
        <ForwardedIconComponent
          name="XCircle"
          className="h-3.5 w-3.5 shrink-0 text-destructive"
        />
        {code ? (
          <button
            onClick={() => setIsCodeExpanded(!isCodeExpanded)}
            className="flex items-center gap-1.5 transition-colors hover:text-foreground"
          >
            <ForwardedIconComponent
              name="ChevronRight"
              className={cn(
                "h-3.5 w-3.5 text-muted-foreground transition-transform",
                isCodeExpanded && "rotate-90",
              )}
            />
            <span className="font-mono text-sm text-destructive">
              Failed: {displayName}
            </span>
          </button>
        ) : (
          <span className="font-mono text-sm text-destructive">
            Failed: {displayName}
          </span>
        )}
      </div>

      {error && (
        <div className="ml-5 font-mono text-xs text-destructive">
          {error}
        </div>
      )}

      {isCodeExpanded && code && (
        <div className="ml-5 mt-1">
          <SimplifiedCodeTabComponent language="python" code={code} />
        </div>
      )}
    </div>
  );
};
