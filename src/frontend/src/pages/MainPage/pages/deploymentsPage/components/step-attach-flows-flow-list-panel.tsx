import { memo } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { FlowType } from "@/types/flow";
import { cn } from "@/utils/utils";
import type { ConnectionItem } from "../types";

export const FlowListPanel = memo(function FlowListPanel({
  flows,
  selectedFlowId,
  selectedVersionByFlow,
  attachedConnectionByFlow,
  connections,
  removedFlowIds,
  onSelectFlow,
  onRemoveFlow,
  onUndoRemoveFlow,
}: {
  flows: FlowType[];
  selectedFlowId: string | null;
  selectedVersionByFlow: Map<string, { versionId: string; versionTag: string }>;
  attachedConnectionByFlow: Map<string, string[]>;
  connections: ConnectionItem[];
  removedFlowIds?: Set<string>;
  onSelectFlow: (flowId: string) => void;
  onRemoveFlow?: (flowId: string) => void;
  onUndoRemoveFlow?: (flowId: string) => void;
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
          const attached = selectedVersionByFlow.has(flow.id);
          const isRemoved = removedFlowIds?.has(flow.id) ?? false;
          const connectionIds = attachedConnectionByFlow.get(flow.id) ?? [];
          const connectionNames = connectionIds
            .map((cid) => connections.find((c) => c.id === cid)?.name)
            .filter(Boolean);
          return (
            <button
              key={flow.id}
              type="button"
              data-testid={`flow-item-${flow.id}`}
              onClick={() => onSelectFlow(flow.id)}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors",
                isRemoved && "opacity-50",
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
                  {versionLabel && !isRemoved && (
                    <Badge
                      variant="secondaryStatic"
                      size="tag"
                      className="bg-accent-purple-muted text-accent-purple-muted-foreground"
                    >
                      {versionLabel}
                    </Badge>
                  )}
                  {attached && !isRemoved && (
                    <Badge
                      variant="secondaryStatic"
                      size="tag"
                      className="bg-accent-blue-muted text-accent-blue-muted-foreground"
                    >
                      ATTACHED
                    </Badge>
                  )}
                  {isRemoved && (
                    <Badge
                      variant="secondaryStatic"
                      size="tag"
                      className="bg-destructive/10 text-destructive"
                    >
                      REMOVED
                    </Badge>
                  )}
                </div>
                {connectionNames.length > 0 && !isRemoved && (
                  <p className="truncate text-xs text-muted-foreground">
                    {connectionNames.join(", ")}
                  </p>
                )}
              </div>
              {attached && !isRemoved && onRemoveFlow && (
                <button
                  type="button"
                  data-testid={`detach-flow-${flow.id}`}
                  className="flex-shrink-0 rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  title="Detach flow"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemoveFlow(flow.id);
                  }}
                >
                  <ForwardedIconComponent name="X" className="h-3.5 w-3.5" />
                </button>
              )}
              {isRemoved && onUndoRemoveFlow && (
                <button
                  type="button"
                  data-testid={`undo-remove-flow-${flow.id}`}
                  className="flex-shrink-0 rounded p-1 text-muted-foreground hover:bg-accent-blue-muted hover:text-accent-blue-muted-foreground"
                  title="Undo detach"
                  onClick={(e) => {
                    e.stopPropagation();
                    onUndoRemoveFlow(flow.id);
                  }}
                >
                  <ForwardedIconComponent
                    name="Undo2"
                    className="h-3.5 w-3.5"
                  />
                </button>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
});
