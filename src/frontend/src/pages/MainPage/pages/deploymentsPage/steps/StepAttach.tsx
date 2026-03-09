import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Checkbox } from "@/components/ui/checkbox";

type CheckpointAttachItem = {
  id: string;
  name: string;
  updatedDate: string;
};

type FlowAttachItem = {
  flowId: string;
  flowName: string;
  checkpoints: CheckpointAttachItem[];
};

type StepAttachProps = {
  selectedItems: Set<string>;
  toggleItem: (id: string) => void;
  flows: FlowAttachItem[];
};

export const StepAttach = ({
  selectedItems,
  toggleItem,
  flows,
}: StepAttachProps) => {
  const [expandedFlowIds, setExpandedFlowIds] = useState<Set<string>>(
    new Set(),
  );

  useEffect(() => {
    const firstFlowId = flows[0]?.flowId;
    setExpandedFlowIds(firstFlowId ? new Set([firstFlowId]) : new Set());
  }, [flows]);

  const toggleFlow = (flowId: string) => {
    setExpandedFlowIds((prev) => {
      const next = new Set(prev);
      if (next.has(flowId)) {
        next.delete(flowId);
      } else {
        next.add(flowId);
      }
      return next;
    });
  };

  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <h3 className="text-base font-semibold">Attach Checkpoints</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Select one or more existing flow-version checkpoints to include
        </p>
      </div>
      <div className="flex flex-col gap-2 overflow-y-auto">
        {flows.map((flow) => {
          const isExpanded = expandedFlowIds.has(flow.flowId);
          return (
            <div key={flow.flowId} className="rounded-lg border border-border">
              <button
                type="button"
                onClick={() => toggleFlow(flow.flowId)}
                className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-muted/30"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <ForwardedIconComponent
                    name={isExpanded ? "ChevronDown" : "ChevronRight"}
                    className="h-4 w-4 shrink-0 text-muted-foreground"
                  />
                  <span className="truncate text-sm font-semibold">
                    {flow.flowName}
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {flow.checkpoints.length} checkpoint
                  {flow.checkpoints.length === 1 ? "" : "s"}
                </span>
              </button>
              {isExpanded && (
                <div className="flex flex-col gap-2 border-t border-border p-2">
                  {flow.checkpoints.length > 0 ? (
                    flow.checkpoints.map((checkpoint) => (
                      <button
                        key={checkpoint.id}
                        type="button"
                        onClick={() => toggleItem(checkpoint.id)}
                        className={`flex items-start gap-3 rounded-lg border p-3 text-left transition-colors ${
                          selectedItems.has(checkpoint.id)
                            ? "border-2 border-primary"
                            : "border-border hover:border-muted-foreground"
                        }`}
                      >
                        <Checkbox
                          checked={selectedItems.has(checkpoint.id)}
                          className="mt-0.5 pointer-events-none"
                        />
                        <div className="flex flex-col gap-0.5">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold">
                              {checkpoint.name}
                            </span>
                            <span className="inline-flex items-center rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                              Checkpoint
                            </span>
                          </div>
                          <span className="text-xs text-muted-foreground">
                            Created: {checkpoint.updatedDate}
                          </span>
                        </div>
                      </button>
                    ))
                  ) : (
                    <p className="px-2 py-1 text-sm text-muted-foreground">
                      No checkpoints found for this flow.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {flows.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No history checkpoints available.
          </p>
        )}
      </div>
      {selectedItems.size === 0 && (
        <p className="mt-auto text-center text-sm text-muted-foreground">
          Select at least one checkpoint to continue
        </p>
      )}
    </div>
  );
};
