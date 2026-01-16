import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import { downloadComponentFile } from "../helpers/file-download";

type ComponentResultLineProps = {
  className: string;
  code: string;
  onAddToCanvas: (code: string) => Promise<void>;
};

export const ComponentResultLine = ({
  className,
  code,
  onAddToCanvas,
}: ComponentResultLineProps) => {
  const [isAddingToCanvas, setIsAddingToCanvas] = useState(false);
  const [isCodeExpanded, setIsCodeExpanded] = useState(false);

  const handleDownload = () => {
    downloadComponentFile(code, className);
  };

  const handleAddToCanvas = async () => {
    setIsAddingToCanvas(true);
    try {
      await onAddToCanvas(code);
    } finally {
      setIsAddingToCanvas(false);
    }
  };

  return (
    <div className="flex flex-col gap-2 py-2">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setIsCodeExpanded(!isCodeExpanded)}
          className="flex items-center gap-1.5 transition-colors hover:text-foreground"
        >
          <ForwardedIconComponent
            name="ChevronRight"
            className={cn(
              "h-4 w-4 text-muted-foreground transition-transform",
              isCodeExpanded && "rotate-90",
            )}
          />
          <span className="font-mono text-sm text-accent-emerald-foreground">
            {className}.py
          </span>
        </button>

        <div className="flex items-center gap-0.5">
          <Button
            variant="ghost"
            size="iconSm"
            onClick={handleDownload}
            className="text-muted-foreground hover:bg-muted hover:text-foreground"
            title="Download"
          >
            <ForwardedIconComponent name="Download" className="h-3.5 w-3.5" />
          </Button>

          <Button
            variant="ghost"
            size="iconSm"
            onClick={handleAddToCanvas}
            disabled={isAddingToCanvas}
            className="ml-1 bg-accent-emerald-foreground/15 text-accent-emerald-foreground hover:bg-accent-emerald-foreground/25 disabled:opacity-50"
            title="Add to Canvas"
          >
            <ForwardedIconComponent
              name={isAddingToCanvas ? "Loader2" : "Plus"}
              className={cn("h-3.5 w-3.5", isAddingToCanvas && "animate-spin")}
            />
          </Button>
        </div>
      </div>

      {isCodeExpanded && (
        <div className="mt-1">
          <SimplifiedCodeTabComponent language="python" code={code} />
        </div>
      )}
    </div>
  );
};
