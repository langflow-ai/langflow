import { cloneDeep } from "lodash";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { getFlowRevision } from "@/controllers/API/queries/flow-revisions";
import useFlowStore from "@/stores/flowStore";
import useRevisionPlaybackStore from "@/stores/revisionPlaybackStore";
import {
  applyFlowOperations,
  type FlowGraph,
} from "@/utils/flow-operations/apply";
import { describeOperation } from "@/utils/flow-operations/describe";
import { processFlows } from "@/utils/reactflowUtils";

type Steps = { graphs: FlowGraph[] } | { error: true } | null;

function showOnCanvas(graph: FlowGraph) {
  // biome-ignore lint/suspicious/noExplicitAny: processFlows takes the legacy flow shape
  const flow = { data: cloneDeep(graph), is_component: false } as any;
  processFlows([flow]);
  useFlowStore.setState({ nodes: flow.data.nodes, edges: flow.data.edges });
}

/**
 * Steps through the previewed timeline entry one operation at a time.
 *
 * It loads the flow as it was just before the entry and applies the entry's
 * recorded operations with the same rules the server uses, keeping the graph
 * after each one. Operations are copy-on-write, so those graphs share
 * everything that did not change, and moving the slider either way is a
 * lookup. Preview and restore still refer to the entry's end; the steps in
 * between are only shown.
 */
export default function RevisionPlayback() {
  const { t } = useTranslation();
  const entry = useRevisionPlaybackStore((state) => state.entry);
  const [steps, setSteps] = useState<Steps>(null);
  const [position, setPosition] = useState(0);

  useEffect(() => {
    setSteps(null);
    if (!entry) return;
    let cancelled = false;
    getFlowRevision(entry.flowId, entry.fromRevision)
      .then(({ data }) => {
        const graphs = [data as FlowGraph];
        for (const recorded of entry.operations) {
          graphs.push(
            applyFlowOperations(graphs[graphs.length - 1], [recorded.operation])
              .flowData,
          );
        }
        if (!cancelled) {
          setSteps({ graphs });
          setPosition(graphs.length - 1);
        }
      })
      .catch(() => {
        // The revision before the entry may no longer be retained, or the
        // operations may not replay; the entry's end is still previewed.
        if (!cancelled) setSteps({ error: true });
      });
    return () => {
      cancelled = true;
    };
  }, [entry]);

  const current = useMemo(
    () => (entry && position > 0 ? entry.operations[position - 1] : undefined),
    [entry, position],
  );

  if (!entry || entry.operations.length === 0) return null;

  if (steps && "error" in steps) {
    return (
      <div className="pointer-events-auto absolute right-4 top-1/2 flex -translate-y-1/2 items-center gap-2 rounded-lg border bg-background px-3 py-2 text-xs text-muted-foreground shadow">
        <ForwardedIconComponent name="CircleSlash" className="h-3.5 w-3.5" />
        {t("flowHistory.playback.unavailable")}
      </div>
    );
  }

  const lastStep = entry.operations.length;
  const onMove = (next: number) => {
    if (!steps || "error" in steps) return;
    setPosition(next);
    showOnCanvas(steps.graphs[next]);
  };

  return (
    <div className="pointer-events-auto absolute right-4 top-1/2 flex w-56 -translate-y-1/2 flex-col items-center gap-2 rounded-lg border bg-background p-3 shadow">
      <span className="text-xs font-medium">
        {t("flowHistory.playback.title")}
      </span>
      <span className="text-xs text-muted-foreground">
        {t("flowHistory.playback.step", { step: position, total: lastStep })}
      </span>
      <input
        type="range"
        aria-label={t("flowHistory.playback.title")}
        min={0}
        max={lastStep}
        step={1}
        value={position}
        disabled={!steps}
        onChange={(event) => onMove(Number(event.target.value))}
        // Vertical, newest at the top, like the timeline beside it.
        className="h-40 cursor-pointer accent-primary [direction:rtl] [writing-mode:vertical-lr]"
      />
      <div className="flex gap-1">
        <button
          type="button"
          className="rounded p-1 hover:bg-muted disabled:opacity-40"
          disabled={!steps || position === 0}
          onClick={() => onMove(position - 1)}
          aria-label={t("flowHistory.playback.back")}
        >
          <ForwardedIconComponent name="ChevronDown" className="h-4 w-4" />
        </button>
        <button
          type="button"
          className="rounded p-1 hover:bg-muted disabled:opacity-40"
          disabled={!steps || position === lastStep}
          onClick={() => onMove(position + 1)}
          aria-label={t("flowHistory.playback.forward")}
        >
          <ForwardedIconComponent name="ChevronUp" className="h-4 w-4" />
        </button>
      </div>
      <span className="min-h-8 text-center text-xs text-muted-foreground">
        {current
          ? `${current.actor.username ?? t("flowHistory.unknownAuthor")}: ${describeOperation(current, t).join("; ")}`
          : t("flowHistory.playback.before")}
      </span>
    </div>
  );
}
