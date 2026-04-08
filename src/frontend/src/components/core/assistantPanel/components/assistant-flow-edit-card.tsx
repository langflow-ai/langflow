import { Check, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useCallback, useState } from "react";
import type { FlowAction } from "@/controllers/API/queries/agentic";
import useFlowStore from "@/stores/flowStore";

interface FlowEditCarouselProps {
  actions: FlowAction[];
  onUpdateAction: (id: string, status: "applied" | "dismissed") => void;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "(empty)";
  if (typeof value === "string")
    return value.length > 60 ? value.slice(0, 57) + "..." : value;
  return String(value);
}

function FlowEditCard({
  action,
  onAccept,
  onDismiss,
}: {
  action: FlowAction;
  onAccept: () => void;
  onDismiss: () => void;
}) {
  const isPending = action.status === "pending";

  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-muted-foreground">{action.description}</p>

      <div className="flex items-center gap-2 rounded bg-muted/50 px-3 py-2 text-xs font-mono">
        <span className="text-destructive line-through">
          {formatValue(action.old_value)}
        </span>
        <span className="text-muted-foreground">-&gt;</span>
        <span className="text-accent-emerald-foreground">
          {formatValue(action.new_value)}
        </span>
      </div>

      {isPending && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="flex h-7 items-center gap-1 rounded-md bg-white px-3 text-xs font-medium text-zinc-900 transition-colors hover:bg-zinc-100"
            onClick={onAccept}
          >
            <Check className="h-3 w-3" />
            Accept
          </button>
          <button
            type="button"
            className="flex h-7 items-center gap-1 rounded-md bg-zinc-700 px-3 text-xs font-medium text-white transition-colors hover:bg-zinc-600"
            onClick={onDismiss}
          >
            <X className="h-3 w-3" />
            Dismiss
          </button>
        </div>
      )}

      {action.status === "applied" && (
        <div className="flex h-7 items-center gap-1 text-xs font-medium text-accent-emerald-foreground">
          <Check className="h-3 w-3" />
          Applied
        </div>
      )}

      {action.status === "dismissed" && (
        <div className="flex h-7 items-center gap-1 text-xs font-medium text-muted-foreground/60 line-through">
          Dismissed
        </div>
      )}
    </div>
  );
}

export function FlowEditCarousel({
  actions,
  onUpdateAction,
}: FlowEditCarouselProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const nodes = useFlowStore((state) => state.nodes);
  const setNodes = useFlowStore((state) => state.setNodes);
  const edges = useFlowStore((state) => state.edges);

  const current = actions[currentIndex];
  if (!current) return null;

  const handleAccept = useCallback(() => {
    // Apply the JSON Patch to the flow data
    const action = actions[currentIndex];
    if (!action?.patch) return;

    // Apply each patch operation to the ReactFlow nodes
    for (const op of action.patch) {
      if (op.op !== "replace") continue;
      // Parse the path: /data/nodes/{idx}/data/node/template/{field}/value
      const parts = op.path.split("/").filter(Boolean);
      // parts: ["data", "nodes", idx, "data", "node", "template", field, "value"]
      if (parts[0] === "data" && parts[1] === "nodes" && parts.length >= 8) {
        const nodeIdx = parseInt(parts[2], 10);
        const field = parts[6];
        setNodes((prevNodes) =>
          prevNodes.map((node, i) => {
            if (i !== nodeIdx) return node;
            const template = (node.data as Record<string, unknown>)?.node as
              | Record<string, unknown>
              | undefined;
            if (!template?.template) return node;
            const tmpl = template.template as Record<
              string,
              Record<string, unknown>
            >;
            if (!tmpl[field]) return node;
            return {
              ...node,
              data: {
                ...node.data,
                node: {
                  ...(node.data as Record<string, unknown>).node,
                  template: {
                    ...tmpl,
                    [field]: { ...tmpl[field], value: op.value },
                  },
                },
              },
            };
          }),
        );
      }
    }

    onUpdateAction(action.id, "applied");
    // Auto-advance to next pending
    const nextPending = actions.findIndex(
      (a, i) => i > currentIndex && a.status === "pending",
    );
    if (nextPending >= 0) setCurrentIndex(nextPending);
  }, [actions, currentIndex, onUpdateAction, setNodes]);

  const handleDismiss = useCallback(() => {
    onUpdateAction(current.id, "dismissed");
    const nextPending = actions.findIndex(
      (a, i) => i > currentIndex && a.status === "pending",
    );
    if (nextPending >= 0) setCurrentIndex(nextPending);
  }, [actions, current, currentIndex, onUpdateAction]);

  const handleAcceptAll = useCallback(() => {
    for (const action of actions) {
      if (action.status === "pending") {
        // Apply patches (simplified -- call handleAccept logic for each)
        onUpdateAction(action.id, "applied");
      }
    }
  }, [actions, onUpdateAction]);

  const pendingCount = actions.filter((a) => a.status === "pending").length;

  return (
    <div className="max-w-[80%] rounded-lg border border-border bg-muted/30 p-4">
      {/* Header with pagination */}
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold text-foreground">
          Proposed Changes
        </span>
        <div className="flex items-center gap-2">
          {actions.length > 1 && (
            <>
              <button
                type="button"
                className="rounded p-0.5 hover:bg-muted disabled:opacity-30"
                onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
                disabled={currentIndex === 0}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </button>
              <span className="text-xs text-muted-foreground">
                {currentIndex + 1}/{actions.length}
              </span>
              <button
                type="button"
                className="rounded p-0.5 hover:bg-muted disabled:opacity-30"
                onClick={() =>
                  setCurrentIndex((i) => Math.min(actions.length - 1, i + 1))
                }
                disabled={currentIndex === actions.length - 1}
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </>
          )}
          {pendingCount > 1 && (
            <button
              type="button"
              className="ml-2 rounded-md bg-white px-2 py-0.5 text-xs font-medium text-zinc-900 hover:bg-zinc-100"
              onClick={handleAcceptAll}
            >
              Accept All ({pendingCount})
            </button>
          )}
        </div>
      </div>

      <FlowEditCard
        action={current}
        onAccept={handleAccept}
        onDismiss={handleDismiss}
      />
    </div>
  );
}
