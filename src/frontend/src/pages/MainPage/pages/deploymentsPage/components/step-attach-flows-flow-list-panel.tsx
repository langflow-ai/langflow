import { memo } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { FlowType } from "@/types/flow";
import { cn } from "@/utils/utils";

export const FlowListPanel = memo(function FlowListPanel({
  flows,
  selectedFlowId,
  selectedVersionByFlow,
  attachedConnectionByFlow,
  onSelectFlow,
}: {
  flows: FlowType[];
  selectedFlowId: string | null;
  selectedVersionByFlow: Map<string, { versionId: string; versionTag: string }>;
  attachedConnectionByFlow: Map<string, string[]>;
  onSelectFlow: (flowId: string) => void;
}) {
  return (
    <div className="flex w-[280px] flex-shrink-0 flex-col border-r border-border">
      <div className="border-b border-border p-4 text-sm text-muted-foreground">
        Available Flows
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto p-2">
        {flows.map((flow) => {
          const entry = selectedVersionByFlow.get(flow.id);
          const versionLabel = entry?.versionTag || null;
          const attached = attachedConnectionByFlow.has(flow.id);
          return (
            <button
              key={flow.id}
              type="button"
              data-testid={`flow-item-${flow.id}`}
              onClick={() => onSelectFlow(flow.id)}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors",
                selectedFlowId === flow.id ? "bg-muted" : "hover:bg-muted/60",
              )}
            >
              <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-border bg-muted">
                <ForwardedIconComponent
                  name={flow.icon ?? "Workflow"}
                  className="h-4 w-4 text-muted-foreground"
                />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="truncate text-sm font-semibold">
                    {flow.name}
                  </span>
                  {versionLabel && (
                    <Badge
                      variant="secondaryStatic"
                      size="tag"
                      className="bg-accent-purple-muted text-accent-purple-muted-foreground"
                    >
                      {versionLabel}
                    </Badge>
                  )}
                  {attached && (
                    <Badge
                      variant="secondaryStatic"
                      size="tag"
                      className="bg-accent-blue-muted text-accent-blue-muted-foreground"
                    >
                      ATTACHED
                    </Badge>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
});
