import { useEffect, useState } from "react";
import { Check, FileText } from "lucide-react";
import type { AgenticResult } from "@/controllers/API/queries/agentic";
import { ViewCodeModal } from "./view-code-modal";

const APPROVED_DISPLAY_DURATION_MS = 3000;

interface AssistantComponentResultProps {
  result: AgenticResult;
  onApprove: () => void;
}

export function AssistantComponentResult({
  result,
  onApprove,
}: AssistantComponentResultProps) {
  const [showApproved, setShowApproved] = useState(false);
  const [isViewCodeOpen, setIsViewCodeOpen] = useState(false);
  const componentName = result.className || "Custom Component";

  useEffect(() => {
    if (showApproved) {
      const timer = setTimeout(() => {
        setShowApproved(false);
      }, APPROVED_DISPLAY_DURATION_MS);
      return () => clearTimeout(timer);
    }
  }, [showApproved]);

  const handleApprove = () => {
    onApprove();
    setShowApproved(true);
  };

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-4">
      {/* Component header */}
      <div className="mb-3 flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-[#0EA5E9]">
          <FileText className="h-4 w-4 text-white" />
        </div>
        <span className="text-sm font-semibold text-foreground">
          {componentName}
        </span>
      </div>

      {/* Features section */}
      <div className="mb-4">
        <h4 className="mb-2 text-xs font-semibold text-foreground">Features</h4>
        <div className="flex flex-col gap-1 pl-4 text-sm text-muted-foreground">
          <span>Input/Output handling with type validation</span>
          <span>Error handling and logging</span>
          <span>Customizable parameters</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {showApproved ? (
          <div className="flex h-8 items-center gap-1.5 text-sm font-medium text-accent-emerald-foreground">
            <Check className="h-4 w-4" />
            <span>Approved</span>
          </div>
        ) : (
          <button
            type="button"
            className="h-8 rounded-[10px] bg-white px-4 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-100"
            onClick={handleApprove}
          >
            Approve
          </button>
        )}
        <button
          type="button"
          className="h-8 rounded-[10px] bg-zinc-700 px-4 text-sm font-medium text-white transition-colors hover:bg-zinc-600"
          onClick={() => setIsViewCodeOpen(true)}
        >
          View Code
        </button>
      </div>

      {result.componentCode && (
        <ViewCodeModal
          code={result.componentCode}
          open={isViewCodeOpen}
          onOpenChange={setIsViewCodeOpen}
        />
      )}
    </div>
  );
}
