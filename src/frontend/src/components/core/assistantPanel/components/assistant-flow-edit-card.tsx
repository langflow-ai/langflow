import { Check, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useCallback, useState } from "react";
import type { FlowAction } from "@/controllers/API/queries/agentic";
import useFlowStore from "@/stores/flowStore";
import {
  GHOST_PRIMARY_BUTTON,
  GHOST_SECONDARY_BUTTON,
} from "../helpers/button-styles";

interface FlowEditCarouselProps {
  actions: FlowAction[];
  onUpdateAction: (id: string, status: "applied" | "dismissed") => void;
}

// Long edit descriptions (the LLM restates the entire new value, e.g. a full
// system_prompt) balloon the card. Above this length the description is
// clamped to a few lines with a Show more/less toggle so the card stays
// compact while the full intent is still one click away before approving.
const DESCRIPTION_CLAMP_CHARS = 160;

const CLAMP_STYLE = {
  display: "-webkit-box",
  WebkitLineClamp: 3,
  WebkitBoxOrient: "vertical" as const,
  overflow: "hidden",
};

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
  const [expanded, setExpanded] = useState(false);
  const fullNew = action.new_value == null ? "" : String(action.new_value);
  const fullOld = action.old_value == null ? "" : String(action.old_value);
  // The summary is a short clean preview, so "Show more" must key off the
  // VALUE: a long / multi-line proposed value still has to be fully
  // reviewable before approving (kept the description-length clause so
  // pre-existing long-summary behavior is preserved).
  const isLong =
    fullNew.length > 80 ||
    fullNew.includes("\n") ||
    (action.description?.length ?? 0) > DESCRIPTION_CLAMP_CHARS;
  const collapsed = isLong && !expanded;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-0.5">
        <p
          className="text-xs text-muted-foreground"
          style={collapsed ? CLAMP_STYLE : undefined}
        >
          {action.description}
        </p>
        {isLong && (
          <button
            type="button"
            className="self-start text-xs font-medium text-primary hover:underline"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "Show less" : "Show more"}
          </button>
        )}
      </div>

      {collapsed ? (
        <div className="flex items-center gap-2 rounded bg-muted/50 px-3 py-2 text-xs font-mono">
          <span className="text-destructive line-through">
            {formatValue(action.old_value)}
          </span>
          <span className="text-muted-foreground">-&gt;</span>
          <span className="text-accent-emerald-foreground">
            {formatValue(action.new_value)}
          </span>
        </div>
      ) : (
        <div className="flex max-h-72 flex-col gap-1 overflow-auto rounded bg-muted/50 px-3 py-2 text-xs font-mono">
          <span className="whitespace-pre-wrap break-words text-destructive line-through">
            {fullOld || "(empty)"}
          </span>
          <span className="text-muted-foreground">-&gt;</span>
          <span className="whitespace-pre-wrap break-words text-accent-emerald-foreground">
            {fullNew || "(empty)"}
          </span>
        </div>
      )}

      {isPending && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            className={GHOST_PRIMARY_BUTTON}
            onClick={onAccept}
          >
            <Check className="h-3 w-3" />
            Accept
          </button>
          <button
            type="button"
            className={GHOST_SECONDARY_BUTTON}
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
  const setNodes = useFlowStore((state) => state.setNodes);

  const current = actions[currentIndex];

  // Apply a single action's JSON Patch to the ReactFlow nodes. Shared by
  // single-Accept and Accept-All so the canvas is actually mutated in
  // both paths (Accept All previously only flagged actions applied,
  // persisting the unchanged canvas — silent data loss).
  const applyActionPatch = useCallback(
    (action: (typeof actions)[number]) => {
      if (!action?.patch) return;
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
    },
    [setNodes],
  );

  const handleAccept = useCallback(() => {
    const action = actions[currentIndex];
    if (!action?.patch) return;
    applyActionPatch(action);
    onUpdateAction(action.id, "applied");
    // Auto-advance to next pending
    const nextPending = actions.findIndex(
      (a, i) => i > currentIndex && a.status === "pending",
    );
    if (nextPending >= 0) setCurrentIndex(nextPending);
  }, [actions, currentIndex, onUpdateAction, applyActionPatch]);

  const handleDismiss = useCallback(() => {
    if (!current) return;
    onUpdateAction(current.id, "dismissed");
    const nextPending = actions.findIndex(
      (a, i) => i > currentIndex && a.status === "pending",
    );
    if (nextPending >= 0) setCurrentIndex(nextPending);
  }, [actions, current, currentIndex, onUpdateAction]);

  const handleAcceptAll = useCallback(() => {
    for (const action of actions) {
      if (action.status === "pending") {
        applyActionPatch(action);
        onUpdateAction(action.id, "applied");
      }
    }
  }, [actions, onUpdateAction, applyActionPatch]);

  const pendingCount = actions.filter((a) => a.status === "pending").length;

  // Guard AFTER all hooks so the hook count is stable across renders
  // (actions grow incrementally as edit_field events arrive).
  if (!current) return null;

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
              className="ml-2 rounded-md bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
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
