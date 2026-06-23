import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import Loading from "@/components/ui/loading";
import { useGetTraceQuery } from "@/controllers/API/queries/traces";
import useFlowStore from "@/stores/flowStore";
import { SpanDetail } from "./SpanDetail";
import { SpanTree } from "./SpanTree";
import { TraceHitlBar } from "./TraceHitlBar";
import { Span, TraceDetailViewProps } from "./types";

/**
 * Single-trace detail view used in the right-side panel.
 * Matches the "Trace Detail" layout (header + span list + span details).
 */
export function TraceDetailView({
  traceId,
  flowName,
  pendingRequest,
  onResolved,
  hasTrace = true,
  pollUpdates = false,
}: TraceDetailViewProps) {
  const { t } = useTranslation();
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);
  // Remember the human's pick so the gate stays in the tree as a resolved step after Approve/Reject
  // instead of vanishing the moment the pending request clears.
  const [resolvedAction, setResolvedAction] = useState<string | null>(null);

  // Why: resume reattaches to the live event stream (the same flowStore signals the canvas renders
  // from), so we show the run executing live — the trace table only catches up once it flushes.
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const flowBuildStatus = useFlowStore((state) => state.flowBuildStatus);
  const flowPool = useFlowStore((state) => state.flowPool);
  const buildStartTime = useFlowStore((state) => state.buildStartTime);
  const nodes = useFlowStore((state) => state.nodes);
  const isResuming = pollUpdates && isBuilding && !pendingRequest;

  // Tick a live elapsed clock while resuming, mirroring the canvas's build timer. The AG-UI resume
  // path doesn't set buildStartTime, so fall back to a local start captured when resuming begins.
  const [liveElapsed, setLiveElapsed] = useState<number | null>(null);
  const localStartRef = useRef<number | null>(null);
  useEffect(() => {
    if (!isResuming) {
      setLiveElapsed(null);
      localStartRef.current = null;
      return;
    }
    const start = buildStartTime ?? localStartRef.current ?? Date.now();
    localStartRef.current = start;
    const tick = () => setLiveElapsed(Date.now() - start);
    tick();
    const interval = setInterval(tick, 100);
    return () => clearInterval(interval);
  }, [isResuming, buildStartTime]);

  // A synthetic paused row has no persisted trace; fetching it would 404.
  const fetchable = hasTrace && !!traceId;
  const { data: trace, isLoading } = useGetTraceQuery(
    { traceId: traceId ?? "" },
    { enabled: fetchable, refetchInterval: pollUpdates ? 3000 : false },
  );

  useEffect(() => {
    setSelectedSpan(null);
    setResolvedAction(null);
  }, [traceId]);

  const summarySpan = useMemo<Span | null>(() => {
    if (!trace) return null;

    const status = isResuming ? "unset" : trace.status;
    const name = trace.name || flowName || "Run Summary";

    return {
      id: trace.id,
      name,
      type: "none",
      status,
      startTime: trace.startTime,
      endTime: trace.endTime,
      latencyMs: isResuming ? liveElapsed : trace.totalLatencyMs,
      inputs: trace.input ?? {},
      outputs: trace.output ?? {},
      tokenUsage:
        trace.totalTokens > 0
          ? {
              promptTokens: 0,
              completionTokens: 0,
              totalTokens: trace.totalTokens,
              cost: trace.totalCost,
            }
          : undefined,
      children: trace.spans ?? [],
    };
  }, [trace, isResuming, liveElapsed, flowName]);

  const treeSpans = useMemo(() => {
    if (!trace || !summarySpan) return [] as Span[];
    // Surface the gate as its own node: "awaiting" while pending, then a resolved step showing the
    // decision after Approve/Reject — so it stays in the completed trace rather than disappearing.
    if (!pendingRequest && !resolvedAction) return [summarySpan];
    const decisionLabel = resolvedAction
      ? resolvedAction.toLowerCase().includes("reject")
        ? "Rejected"
        : "Approved"
      : null;
    const hitlSpan: Span = {
      id: `hitl-${pendingRequest?.request_id ?? trace.id}`,
      name: decisionLabel
        ? `Human In The Loop — ${decisionLabel}`
        : "Human In The Loop",
      type: "none",
      status: resolvedAction ? "ok" : "awaiting_human",
      startTime: trace.endTime ?? trace.startTime,
      latencyMs: null,
      inputs: {},
      outputs: resolvedAction ? { decision: resolvedAction } : {},
      children: [],
    };
    return [{ ...summarySpan, children: [...summarySpan.children, hitlSpan] }];
  }, [trace, summarySpan, pendingRequest, resolvedAction]);

  // Why: overlay each span's live build state so the tree behaves like the canvas — BUILDING shows
  // a spinner with no duration (not a stale "0 ms"); BUILT shows the duration streamed in flowPool.
  const nameToNodeId = useMemo(() => {
    const map = new Map<string, string>();
    nodes.forEach((node) => {
      const displayName = node.data?.node?.display_name;
      if (displayName) map.set(displayName.toLowerCase(), node.id);
    });
    return map;
  }, [nodes]);

  const displayedSpans = useMemo(() => {
    if (!isResuming) return treeSpans;
    const liveDuration = (nodeId: string): number | null => {
      const entries = flowPool[nodeId];
      const timedelta = entries?.[entries.length - 1]?.data?.timedelta;
      // timedelta is in SECONDS in the AG-UI node output; latencyMs is milliseconds.
      return typeof timedelta === "number" ? timedelta * 1000 : null;
    };
    const overlay = (span: Span): Span => {
      const nodeId = nameToNodeId.get(span.name.toLowerCase());
      const live = nodeId ? flowBuildStatus[nodeId]?.status : undefined;
      const children = span.children.map(overlay);
      if (live === "BUILDING")
        return { ...span, status: "unset", latencyMs: null, children };
      if (live === "ERROR") return { ...span, status: "error", children };
      if (live === "BUILT")
        return {
          ...span,
          status: "ok",
          latencyMs: (nodeId ? liveDuration(nodeId) : null) ?? span.latencyMs,
          children,
        };
      return { ...span, children };
    };
    return treeSpans.map(overlay);
  }, [treeSpans, isResuming, flowBuildStatus, flowPool, nameToNodeId]);

  useEffect(() => {
    if (!summarySpan) return;
    // Why: re-resolve the selection to the live tree node by id so its detail refreshes as the
    // run finishes, and recover to the summary when the node is gone (the HITL node vanishes after
    // Approve) — otherwise the panel sticks on stale/empty data instead of showing the result.
    setSelectedSpan((prev) => {
      if (!prev) return summarySpan;
      const findById = (spans: Span[]): Span | null => {
        for (const span of spans) {
          if (span.id === prev.id) return span;
          const found = findById(span.children ?? []);
          if (found) return found;
        }
        return null;
      };
      return findById(displayedSpans) ?? summarySpan;
    });
  }, [summarySpan, displayedSpans]);

  const handleSelectSpan = useCallback((span: Span) => {
    setSelectedSpan(span);
  }, []);

  if (!traceId) {
    return (
      <div
        className="flex h-full items-center justify-center text-sm text-muted-foreground"
        data-testid="trace-detail-view-empty"
      >
        {t("trace.noTraceAvailable")}
      </div>
    );
  }

  if (!fetchable) {
    return (
      <div
        className="flex h-full flex-col overflow-hidden"
        data-testid="trace-detail-view-pending"
      >
        <div className="border-b border-border px-4 py-3 pr-12">
          <div className="flex min-w-0 items-center gap-2 overflow-hidden whitespace-nowrap">
            <span className="shrink-0 text-sm font-medium">
              {t("trace.traceDetails")}
            </span>
            <span className="shrink-0 text-sm text-muted-foreground">—</span>
            <span className="shrink-0 text-sm font-medium">
              {flowName ?? traceId}
            </span>
          </div>
        </div>
        <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-muted-foreground">
          {t(
            "trace.pausedRunBody",
            "The flow is paused and waiting for your decision before continuing.",
          )}
        </div>
        {pendingRequest && (
          <TraceHitlBar
            pending={pendingRequest}
            onResolved={onResolved}
            onDecision={setResolvedAction}
          />
        )}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div
        className="flex h-full items-center justify-center"
        data-testid="trace-detail-view-loading"
      >
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <Loading size={32} className="text-primary" />
          <span className="text-sm">{t("trace.loadingTrace")}</span>
        </div>
      </div>
    );
  }

  if (!trace) {
    return (
      <div
        className="flex h-full items-center justify-center text-sm text-muted-foreground"
        data-testid="trace-detail-view-error"
      >
        {t("trace.failedToLoad")}
      </div>
    );
  }

  return (
    <div
      className="flex h-full flex-col overflow-hidden"
      data-testid="trace-detail-view"
    >
      <div className="border-b border-border px-4 py-3 pr-12">
        <div className="flex flex-nowrap items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-2 overflow-hidden whitespace-nowrap">
            <span className="shrink-0 text-sm font-medium">
              {t("trace.traceDetails")}
            </span>
            <span className="shrink-0 text-sm text-muted-foreground">—</span>
            <span className="shrink-0 text-sm font-medium">{trace.id}</span>
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-[380px] min-w-[320px] overflow-y-auto border-r border-border p-2">
          <SpanTree
            spans={displayedSpans}
            selectedSpanId={selectedSpan?.id ?? null}
            onSelectSpan={handleSelectSpan}
          />
        </div>
        <div className="flex-1 overflow-hidden">
          <SpanDetail span={selectedSpan} />
        </div>
      </div>

      {pendingRequest && (
        <TraceHitlBar
          pending={pendingRequest}
          onResolved={onResolved}
          onDecision={setResolvedAction}
        />
      )}
    </div>
  );
}
