# Feature 3: Logs, Messages & Traces Frontend

## Summary

Adds a complete frontend system for viewing execution logs, messages, and traces within the Flow page. This includes:

- **Traces API layer**: React Query hooks for fetching trace lists and individual trace details from the backend.
- **TraceView components**: A split-panel trace viewer with a hierarchical span tree on the left and span detail panel on the right. Each span shows type-specific icons, latency, token usage, cost, and input/output data.
- **LogsMainContent**: A main content area that replaces the canvas when the Logs sidebar section is active. Includes a tabbed interface switching between a logs table view (all runs) and a traces detail view (execution tree for a selected run).
- **MessagesMainContent**: A main content area for viewing messages grouped by session, with inline editing and deletion support via AG Grid table.
- **LogsSidebarGroup**: Sidebar group with Logs/Traces tabs and a trace selector list.
- **MessagesSidebarGroup**: Sidebar group showing sessions grouped by session_id with message counts and timestamps.
- **FlowLogsModal enhancement**: The existing logs modal now includes a Logs/Traces tab switcher, with the Traces tab rendering the full TraceView component.

## Dependencies

- Feature 6 (Sidebar Navigation Restructuring) - the sidebar sections "logs" and "messages" must exist for this feature to be accessible.
- Backend traces API endpoint (referenced as `getURL("TRACES")` in constants).
- Existing `useGetTransactionsQuery` and `useGetMessagesQuery` hooks.
- AG Grid table component (`TableComponent`).
- Existing UI primitives: `Badge`, `Loading`, `Tabs`, `Select`, `Table`.

## File Diffs

### `src/frontend/src/controllers/API/queries/traces/index.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/traces/index.ts b/src/frontend/src/controllers/API/queries/traces/index.ts
new file mode 100644
index 0000000000..c7656eb2ec
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/traces/index.ts
@@ -0,0 +1,2 @@
+export * from "./use-get-traces";
+export * from "./use-get-trace";
```

### `src/frontend/src/controllers/API/queries/traces/use-get-traces.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/traces/use-get-traces.ts b/src/frontend/src/controllers/API/queries/traces/use-get-traces.ts
new file mode 100644
index 0000000000..fd8765f7d4
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/traces/use-get-traces.ts
@@ -0,0 +1,71 @@
+import { keepPreviousData } from "@tanstack/react-query";
+import type { useQueryFunctionType } from "../../../../types/api";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+
+interface TracesQueryParams {
+  flowId: string | null;
+  sessionId?: string | null;
+  params?: Record<string, unknown>;
+}
+
+interface TraceListItem {
+  id: string;
+  name: string;
+  status: string;
+  startTime: string;
+  endTime?: string;
+  totalLatencyMs: number;
+  totalTokens: number;
+  totalCost: number;
+  flowId: string;
+  sessionId?: string;
+}
+
+interface TracesResponse {
+  traces: TraceListItem[];
+  total: number;
+}
+
+export const useGetTracesQuery: useQueryFunctionType<
+  TracesQueryParams,
+  TracesResponse
+> = ({ flowId, sessionId, params }, options) => {
+  const { query } = UseRequestProcessor();
+
+  const getTracesFn = async (): Promise<TracesResponse> => {
+    if (!flowId) return { traces: [], total: 0 };
+
+    const config: { params: Record<string, unknown> } = {
+      params: { flow_id: flowId },
+    };
+
+    if (sessionId) {
+      config.params.session_id = sessionId;
+    }
+
+    if (params) {
+      config.params = { ...config.params, ...params };
+    }
+
+    const result = await api.get<TracesResponse>(
+      `${getURL("TRACES")}`,
+      config,
+    );
+
+    return result.data;
+  };
+
+  const queryResult = query(
+    ["useGetTracesQuery", flowId, sessionId, { ...params }],
+    getTracesFn,
+    {
+      placeholderData: keepPreviousData,
+      refetchOnWindowFocus: false,
+      ...options,
+    },
+  );
+
+  return queryResult;
+};
```

### `src/frontend/src/controllers/API/queries/traces/use-get-trace.ts` (new)

```diff
diff --git a/src/frontend/src/controllers/API/queries/traces/use-get-trace.ts b/src/frontend/src/controllers/API/queries/traces/use-get-trace.ts
new file mode 100644
index 0000000000..75c6554d47
--- /dev/null
+++ b/src/frontend/src/controllers/API/queries/traces/use-get-trace.ts
@@ -0,0 +1,113 @@
+import type { useQueryFunctionType } from "../../../../types/api";
+import type { Trace, Span } from "../../../../modals/flowLogsModal/components/TraceView/types";
+import { api } from "../../api";
+import { getURL } from "../../helpers/constants";
+import { UseRequestProcessor } from "../../services/request-processor";
+
+interface TraceQueryParams {
+  traceId: string | null;
+}
+
+interface TraceApiResponse {
+  id: string;
+  name: string;
+  status: string;
+  startTime: string;
+  endTime?: string;
+  totalLatencyMs: number;
+  totalTokens: number;
+  totalCost: number;
+  flowId: string;
+  sessionId?: string;
+  spans: SpanApiResponse[];
+}
+
+interface SpanApiResponse {
+  id: string;
+  name: string;
+  type: string;
+  status: string;
+  startTime: string;
+  endTime?: string;
+  latencyMs: number;
+  inputs: Record<string, unknown>;
+  outputs: Record<string, unknown>;
+  error?: string;
+  modelName?: string;
+  tokenUsage?: {
+    promptTokens: number;
+    completionTokens: number;
+    totalTokens: number;
+    cost: number;
+  };
+  children: SpanApiResponse[];
+}
+
+/**
+ * Convert API span response to frontend Span type
+ */
+function convertSpan(apiSpan: SpanApiResponse): Span {
+  return {
+    id: apiSpan.id,
+    name: apiSpan.name,
+    type: apiSpan.type as Span["type"],
+    status: apiSpan.status as Span["status"],
+    startTime: apiSpan.startTime,
+    endTime: apiSpan.endTime,
+    latencyMs: apiSpan.latencyMs,
+    inputs: apiSpan.inputs,
+    outputs: apiSpan.outputs,
+    error: apiSpan.error,
+    modelName: apiSpan.modelName,
+    tokenUsage: apiSpan.tokenUsage,
+    children: apiSpan.children?.map(convertSpan) ?? [],
+  };
+}
+
+/**
+ * Convert API trace response to frontend Trace type
+ */
+function convertTrace(apiTrace: TraceApiResponse): Trace | null {
+  if (!apiTrace.spans || apiTrace.spans.length === 0) return null;
+
+  return {
+    id: apiTrace.id,
+    name: apiTrace.name,
+    status: apiTrace.status as Trace["status"],
+    startTime: apiTrace.startTime,
+    endTime: apiTrace.endTime,
+    totalLatencyMs: apiTrace.totalLatencyMs,
+    totalTokens: apiTrace.totalTokens,
+    totalCost: apiTrace.totalCost,
+    spans: apiTrace.spans.map(convertSpan),
+  };
+}
+
+export const useGetTraceQuery: useQueryFunctionType<
+  TraceQueryParams,
+  Trace | null
+> = ({ traceId }, options) => {
+  const { query } = UseRequestProcessor();
+
+  const getTraceFn = async (): Promise<Trace | null> => {
+    if (!traceId) return null;
+
+    const result = await api.get<TraceApiResponse>(
+      `${getURL("TRACES")}/${traceId}`,
+    );
+
+    return convertTrace(result.data);
+  };
+
+  const queryResult = query(
+    ["useGetTraceQuery", traceId],
+    getTraceFn,
+    {
+      refetchOnWindowFocus: false,
+      enabled: !!traceId,
+      ...options,
+    },
+  );
+
+  return queryResult;
+};
```

### `src/frontend/src/modals/flowLogsModal/components/TraceView/types.ts` (new)

```diff
diff --git a/src/frontend/src/modals/flowLogsModal/components/TraceView/types.ts b/src/frontend/src/modals/flowLogsModal/components/TraceView/types.ts
new file mode 100644
index 0000000000..2f1826d0b3
--- /dev/null
+++ b/src/frontend/src/modals/flowLogsModal/components/TraceView/types.ts
@@ -0,0 +1,38 @@
+export type SpanType = "chain" | "llm" | "tool" | "retriever" | "embedding" | "parser" | "agent";
+
+export type SpanStatus = "success" | "error" | "running";
+
+export interface TokenUsage {
+  promptTokens: number;
+  completionTokens: number;
+  totalTokens: number;
+  cost: number;
+}
+
+export interface Span {
+  id: string;
+  name: string;
+  type: SpanType;
+  status: SpanStatus;
+  startTime: string;
+  endTime?: string;
+  latencyMs: number;
+  inputs: Record<string, unknown>;
+  outputs: Record<string, unknown>;
+  error?: string;
+  modelName?: string;
+  tokenUsage?: TokenUsage;
+  children: Span[];
+}
+
+export interface Trace {
+  id: string;
+  name: string;
+  status: SpanStatus;
+  startTime: string;
+  endTime?: string;
+  totalLatencyMs: number;
+  totalTokens: number;
+  totalCost: number;
+  spans: Span[];
+}
```

### `src/frontend/src/modals/flowLogsModal/components/TraceView/index.tsx` (new)

```diff
diff --git a/src/frontend/src/modals/flowLogsModal/components/TraceView/index.tsx b/src/frontend/src/modals/flowLogsModal/components/TraceView/index.tsx
new file mode 100644
index 0000000000..7c4382680b
--- /dev/null
+++ b/src/frontend/src/modals/flowLogsModal/components/TraceView/index.tsx
@@ -0,0 +1,176 @@
+import { useCallback, useEffect, useState } from "react";
+import IconComponent from "@/components/common/genericIconComponent";
+import { Loading } from "@/components/ui/loading";
+import { cn } from "@/utils/utils";
+import type { Span, Trace } from "./types";
+import { SpanTree } from "./SpanTree";
+import { SpanDetail } from "./SpanDetail";
+import { useGetTracesQuery, useGetTraceQuery } from "@/controllers/API/queries/traces";
+
+interface TraceViewProps {
+  flowId?: string | null;
+  initialTraceId?: string | null;
+}
+
+/**
+ * Format total cost as currency
+ */
+function formatTotalCost(cost: number): string {
+  if (cost === 0) return "$0.00";
+  if (cost < 0.01) return `$${cost.toFixed(6)}`;
+  return `$${cost.toFixed(4)}`;
+}
+
+/**
+ * Format total latency
+ */
+function formatTotalLatency(ms: number): string {
+  if (ms < 1000) return `${ms}ms`;
+  return `${(ms / 1000).toFixed(2)}s`;
+}
+
+/**
+ * Main TraceView component showing hierarchical execution traces
+ * Split panel layout: span tree on left, detail panel on right
+ */
+export function TraceView({ flowId, initialTraceId }: TraceViewProps) {
+  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(initialTraceId ?? null);
+  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);
+
+  // Sync selectedTraceId when initialTraceId changes (user clicks different trace in sidebar)
+  useEffect(() => {
+    if (initialTraceId) {
+      setSelectedTraceId(initialTraceId);
+      setSelectedSpan(null);
+    }
+  }, [initialTraceId]);
+
+  // Fetch list of traces for this flow (only needed as fallback if no initialTraceId)
+  const { data: tracesData, isLoading: isLoadingTraces } = useGetTracesQuery(
+    { flowId: flowId ?? null, params: { page: 1, size: 10 } },
+    { enabled: !!flowId && !initialTraceId },
+  );
+
+  // Auto-select the first trace only when no initialTraceId is provided
+  useEffect(() => {
+    if (!initialTraceId && tracesData?.traces && tracesData.traces.length > 0 && !selectedTraceId) {
+      setSelectedTraceId(tracesData.traces[0].id);
+    }
+  }, [tracesData, selectedTraceId, initialTraceId]);
+
+  // Fetch the selected trace with full span tree
+  const { data: trace, isLoading: isLoadingTrace } = useGetTraceQuery(
+    { traceId: selectedTraceId },
+    { enabled: !!selectedTraceId },
+  );
+
+  // Set initial selected span when trace changes
+  useEffect(() => {
+    if (trace?.spans && trace.spans.length > 0) {
+      setSelectedSpan(trace.spans[0]);
+    }
+  }, [trace?.id]);
+
+  const handleSelectSpan = useCallback((span: Span) => {
+    setSelectedSpan(span);
+  }, []);
+
+  const isLoading = isLoadingTraces || isLoadingTrace;
+
+  // Loading state
+  if (isLoading) {
+    return (
+      <div className="flex h-full items-center justify-center">
+        <div className="flex flex-col items-center gap-2 text-muted-foreground">
+          <Loading size={32} className="text-primary" />
+          <span className="text-sm">Loading traces...</span>
+        </div>
+      </div>
+    );
+  }
+
+  // Empty state - no traces available
+  if (!trace || !trace.spans || trace.spans.length === 0) {
+    return (
+      <div className="flex h-full items-center justify-center">
+        <div className="flex flex-col items-center gap-3 text-muted-foreground">
+          <IconComponent name="Activity" className="h-12 w-12 opacity-50" />
+          <div className="text-center">
+            <p className="text-sm font-medium">No traces available</p>
+            <p className="mt-1 text-xs">
+              Run your flow to see execution traces here.
+            </p>
+          </div>
+        </div>
+      </div>
+    );
+  }
+
+  return (
+    <div className="flex h-full flex-col">
+      {/* Trace summary header */}
+      <div className="flex items-center justify-between border-b border-border px-4 py-2">
+        <div className="flex items-center gap-3">
+          <div className="flex items-center gap-2">
+            <IconComponent name="Activity" className="h-4 w-4 text-muted-foreground" />
+            <span className="text-sm font-medium">{trace.name}</span>
+          </div>
+          <span
+            className={cn(
+              "flex items-center gap-1 text-xs",
+              trace.status === "success" && "text-accent-emerald-foreground",
+              trace.status === "error" && "text-error-foreground",
+              trace.status === "running" && "text-muted-foreground",
+            )}
+          >
+            {trace.status === "success" && (
+              <IconComponent name="CheckCircle" className="h-3 w-3" />
+            )}
+            {trace.status === "error" && (
+              <IconComponent name="XCircle" className="h-3 w-3" />
+            )}
+            {trace.status === "running" && (
+              <Loading size={12} className="text-muted-foreground" />
+            )}
+            {trace.status}
+          </span>
+        </div>
+        <div className="flex items-center gap-4 text-xs text-muted-foreground">
+          <span className="flex items-center gap-1">
+            <IconComponent name="Clock" className="h-3 w-3" />
+            {formatTotalLatency(trace.totalLatencyMs)}
+          </span>
+          {trace.totalTokens > 0 && (
+            <span className="flex items-center gap-1">
+              <IconComponent name="Hash" className="h-3 w-3" />
+              {trace.totalTokens.toLocaleString()} tokens
+            </span>
+          )}
+          {trace.totalCost > 0 && (
+            <span className="flex items-center gap-1">
+              <IconComponent name="DollarSign" className="h-3 w-3" />
+              {formatTotalCost(trace.totalCost)}
+            </span>
+          )}
+        </div>
+      </div>
+
+      {/* Main content: split panel */}
+      <div className="flex flex-1 overflow-hidden">
+        {/* Left panel: Span tree */}
+        <div className="w-1/3 min-w-[280px] overflow-y-auto border-r border-border p-2">
+          <SpanTree
+            spans={trace.spans ?? []}
+            selectedSpanId={selectedSpan?.id ?? null}
+            onSelectSpan={handleSelectSpan}
+          />
+        </div>
+
+        {/* Right panel: Span details */}
+        <div className="flex-1 overflow-hidden">
+          <SpanDetail span={selectedSpan} />
+        </div>
+      </div>
+    </div>
+  );
+}
```

### `src/frontend/src/modals/flowLogsModal/components/TraceView/SpanTree.tsx` (new)

```diff
diff --git a/src/frontend/src/modals/flowLogsModal/components/TraceView/SpanTree.tsx b/src/frontend/src/modals/flowLogsModal/components/TraceView/SpanTree.tsx
new file mode 100644
index 0000000000..db4dcfeaa7
--- /dev/null
+++ b/src/frontend/src/modals/flowLogsModal/components/TraceView/SpanTree.tsx
@@ -0,0 +1,71 @@
+import { useCallback, useState } from "react";
+import type { Span } from "./types";
+import { SpanNode } from "./SpanNode";
+
+interface SpanTreeProps {
+  spans: Span[];
+  selectedSpanId: string | null;
+  onSelectSpan: (span: Span) => void;
+}
+
+/**
+ * Recursive tree component for rendering hierarchical spans
+ * Manages expand/collapse state for each node
+ */
+export function SpanTree({
+  spans,
+  selectedSpanId,
+  onSelectSpan,
+}: SpanTreeProps) {
+  // Track which spans are expanded (default: root level expanded)
+  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => {
+    const initial = new Set<string>();
+    // Expand root level spans by default
+    spans.forEach((span) => initial.add(span.id));
+    return initial;
+  });
+
+  const toggleExpand = useCallback((spanId: string) => {
+    setExpandedIds((prev) => {
+      const next = new Set(prev);
+      if (next.has(spanId)) {
+        next.delete(spanId);
+      } else {
+        next.add(spanId);
+      }
+      return next;
+    });
+  }, []);
+
+  /**
+   * Recursively render span nodes
+   */
+  const renderSpan = useCallback(
+    (span: Span, depth: number) => {
+      const isExpanded = expandedIds.has(span.id);
+      const isSelected = span.id === selectedSpanId;
+
+      return (
+        <div key={span.id} role="group">
+          <SpanNode
+            span={span}
+            depth={depth}
+            isExpanded={isExpanded}
+            isSelected={isSelected}
+            onToggle={() => toggleExpand(span.id)}
+            onSelect={() => onSelectSpan(span)}
+          />
+          {isExpanded &&
+            span.children.map((child) => renderSpan(child, depth + 1))}
+        </div>
+      );
+    },
+    [expandedIds, selectedSpanId, toggleExpand, onSelectSpan],
+  );
+
+  return (
+    <div className="flex flex-col" role="tree" aria-label="Trace spans">
+      {spans.map((span) => renderSpan(span, 0))}
+    </div>
+  );
+}
```

### `src/frontend/src/modals/flowLogsModal/components/TraceView/SpanNode.tsx` (new)

```diff
diff --git a/src/frontend/src/modals/flowLogsModal/components/TraceView/SpanNode.tsx b/src/frontend/src/modals/flowLogsModal/components/TraceView/SpanNode.tsx
new file mode 100644
index 0000000000..93d554feb8
--- /dev/null
+++ b/src/frontend/src/modals/flowLogsModal/components/TraceView/SpanNode.tsx
@@ -0,0 +1,164 @@
+import { Badge } from "@/components/ui/badge";
+import IconComponent from "@/components/common/genericIconComponent";
+import { Loading } from "@/components/ui/loading";
+import { cn } from "@/utils/utils";
+import type { Span, SpanType } from "./types";
+
+interface SpanNodeProps {
+  span: Span;
+  depth: number;
+  isExpanded: boolean;
+  isSelected: boolean;
+  onToggle: () => void;
+  onSelect: () => void;
+}
+
+/**
+ * Get the icon name for each span type
+ */
+function getSpanIcon(type: SpanType): string {
+  const iconMap: Record<SpanType, string> = {
+    agent: "Bot",
+    chain: "Link",
+    llm: "MessageSquare",
+    tool: "Wrench",
+    retriever: "Search",
+    embedding: "Hash",
+    parser: "FileText",
+  };
+  return iconMap[type] || "Circle";
+}
+
+/**
+ * Get the badge variant based on status
+ */
+function getStatusVariant(
+  status: Span["status"],
+): "successStatic" | "errorStatic" | "secondaryStatic" {
+  switch (status) {
+    case "success":
+      return "successStatic";
+    case "error":
+      return "errorStatic";
+    case "running":
+      return "secondaryStatic";
+    default:
+      return "secondaryStatic";
+  }
+}
+
+/**
+ * Format latency in a human-readable way
+ */
+function formatLatency(ms: number): string {
+  if (ms === 0) return "...";
+  if (ms < 1000) return `${ms}ms`;
+  return `${(ms / 1000).toFixed(1)}s`;
+}
+
+/**
+ * Format token count with abbreviation for large numbers
+ */
+function formatTokens(tokens: number | undefined): string | null {
+  if (!tokens) return null;
+  if (tokens < 1000) return `${tokens} tok`;
+  return `${(tokens / 1000).toFixed(1)}k tok`;
+}
+
+/**
+ * Single span row in the trace tree
+ * Shows icon, name, latency, token count, and status
+ */
+export function SpanNode({
+  span,
+  depth,
+  isExpanded,
+  isSelected,
+  onToggle,
+  onSelect,
+}: SpanNodeProps) {
+  const hasChildren = span.children.length > 0;
+  const tokenStr = formatTokens(span.tokenUsage?.totalTokens);
+
+  return (
+    <div
+      className={cn(
+        "flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 transition-colors",
+        "hover:bg-muted/50",
+        isSelected && "bg-muted",
+      )}
+      style={{ paddingLeft: `${depth * 16 + 8}px` }}
+      onClick={onSelect}
+      role="treeitem"
+      aria-selected={isSelected}
+      aria-expanded={hasChildren ? isExpanded : undefined}
+    >
+      {/* Expand/collapse button */}
+      <button
+        className={cn(
+          "flex h-4 w-4 items-center justify-center rounded-sm text-muted-foreground transition-colors",
+          hasChildren && "hover:bg-muted-foreground/20",
+          !hasChildren && "invisible",
+        )}
+        onClick={(e) => {
+          e.stopPropagation();
+          if (hasChildren) onToggle();
+        }}
+        tabIndex={-1}
+        aria-hidden={!hasChildren}
+      >
+        <IconComponent
+          name={isExpanded ? "ChevronDown" : "ChevronRight"}
+          className="h-3 w-3"
+        />
+      </button>
+
+      {/* Span type icon */}
+      <div
+        className={cn(
+          "flex h-5 w-5 items-center justify-center rounded",
+          span.status === "error" && "text-error-foreground",
+          span.status === "success" && "text-foreground",
+          span.status === "running" && "text-muted-foreground",
+        )}
+      >
+        <IconComponent name={getSpanIcon(span.type)} className="h-4 w-4" />
+      </div>
+
+      {/* Span name */}
+      <span
+        className={cn(
+          "flex-1 truncate text-sm font-medium",
+          span.status === "error" && "text-error-foreground",
+        )}
+      >
+        {span.name}
+      </span>
+
+      {/* Token count (if applicable) */}
+      {tokenStr && (
+        <span className="text-xs text-muted-foreground">{tokenStr}</span>
+      )}
+
+      {/* Latency */}
+      <span className="min-w-[48px] text-right text-xs text-muted-foreground">
+        {formatLatency(span.latencyMs)}
+      </span>
+
+      {/* Status badge */}
+      <Badge
+        variant={getStatusVariant(span.status)}
+        size="xq"
+        className="min-w-[16px]"
+      >
+        {span.status === "running" ? (
+          <Loading size={12} />
+        ) : span.status === "success" ? (
+          <IconComponent name="Check" className="h-3 w-3" />
+        ) : (
+          <IconComponent name="X" className="h-3 w-3" />
+        )}
+      </Badge>
+    </div>
+  );
+}
```

### `src/frontend/src/modals/flowLogsModal/components/TraceView/SpanDetail.tsx` (new)

```diff
diff --git a/src/frontend/src/modals/flowLogsModal/components/TraceView/SpanDetail.tsx b/src/frontend/src/modals/flowLogsModal/components/TraceView/SpanDetail.tsx
new file mode 100644
index 0000000000..c3ccb1123d
--- /dev/null
+++ b/src/frontend/src/modals/flowLogsModal/components/TraceView/SpanDetail.tsx
@@ -0,0 +1,228 @@
+import { Badge } from "@/components/ui/badge";
+import IconComponent from "@/components/common/genericIconComponent";
+import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
+import { cn } from "@/utils/utils";
+import type { Span, SpanType } from "./types";
+
+interface SpanDetailProps {
+  span: Span | null;
+}
+
+/**
+ * Get display name for span type
+ */
+function getSpanTypeLabel(type: SpanType): string {
+  const labelMap: Record<SpanType, string> = {
+    agent: "Agent",
+    chain: "Chain",
+    llm: "LLM",
+    tool: "Tool",
+    retriever: "Retriever",
+    embedding: "Embedding",
+    parser: "Parser",
+  };
+  return labelMap[type] || type;
+}
+
+/**
+ * Format a cost value as currency
+ */
+function formatCost(cost: number | undefined): string {
+  if (cost === undefined || cost === 0) return "$0.00";
+  if (cost < 0.01) return `$${cost.toFixed(6)}`;
+  return `$${cost.toFixed(4)}`;
+}
+
+/**
+ * Format latency in human-readable format
+ */
+function formatLatency(ms: number): string {
+  if (ms === 0) return "Running...";
+  if (ms < 1000) return `${ms}ms`;
+  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
+  return `${(ms / 60000).toFixed(2)}m`;
+}
+
+/**
+ * Format JSON data for display
+ */
+function formatJsonData(data: Record<string, unknown>): string {
+  try {
+    return JSON.stringify(data, null, 2);
+  } catch {
+    return String(data);
+  }
+}
+
+/**
+ * Detail panel showing full information about a selected span
+ * Includes inputs, outputs, model info, tokens, and errors
+ */
+export function SpanDetail({ span }: SpanDetailProps) {
+  if (!span) {
+    return (
+      <div className="flex h-full items-center justify-center text-muted-foreground">
+        <div className="text-center">
+          <IconComponent name="MousePointer" className="mx-auto mb-2 h-8 w-8" />
+          <p className="text-sm">Select a span to view details</p>
+        </div>
+      </div>
+    );
+  }
+
+  const hasInputs = Object.keys(span.inputs).length > 0;
+  const hasOutputs = Object.keys(span.outputs).length > 0;
+  const hasTokenUsage = span.tokenUsage && span.tokenUsage.totalTokens > 0;
+
+  return (
+    <div className="flex h-full flex-col overflow-hidden">
+      {/* Header */}
+      <div className="border-b border-border px-4 py-3">
+        <div className="flex items-center gap-2">
+          <h3 className="text-lg font-semibold">{span.name}</h3>
+          <Badge
+            variant={
+              span.status === "success"
+                ? "successStatic"
+                : span.status === "error"
+                  ? "errorStatic"
+                  : "secondaryStatic"
+            }
+            size="sm"
+          >
+            {span.status}
+          </Badge>
+        </div>
+        <div className="mt-1 flex items-center gap-4 text-sm text-muted-foreground">
+          <span>{getSpanTypeLabel(span.type)}</span>
+          {span.modelName && (
+            <>
+              <span className="text-border">|</span>
+              <span>{span.modelName}</span>
+            </>
+          )}
+        </div>
+      </div>
+
+      {/* Content */}
+      <div className="flex-1 overflow-y-auto p-4">
+        {/* Error message (if present) */}
+        {span.error && (
+          <div className="mb-4 rounded-md border border-error-foreground/20 bg-error-background/50 p-3">
+            <div className="flex items-center gap-2 text-sm font-medium text-error-foreground">
+              <IconComponent name="AlertCircle" className="h-4 w-4" />
+              Error
+            </div>
+            <p className="mt-1 text-sm text-error-foreground/90">{span.error}</p>
+          </div>
+        )}
+
+        {/* Metrics row */}
+        <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
+          <MetricCard
+            label="Latency"
+            value={formatLatency(span.latencyMs)}
+            icon="Clock"
+          />
+          {hasTokenUsage && (
+            <>
+              <MetricCard
+                label="Tokens"
+                value={span.tokenUsage!.totalTokens.toLocaleString()}
+                icon="Hash"
+              />
+              <MetricCard
+                label="Prompt"
+                value={span.tokenUsage!.promptTokens.toLocaleString()}
+                icon="ArrowUp"
+              />
+              <MetricCard
+                label="Completion"
+                value={span.tokenUsage!.completionTokens.toLocaleString()}
+                icon="ArrowDown"
+              />
+            </>
+          )}
+        </div>
+
+        {/* Cost (if applicable) */}
+        {hasTokenUsage && span.tokenUsage!.cost > 0 && (
+          <div className="mb-4 flex items-center justify-between rounded-md bg-muted p-3">
+            <span className="text-sm font-medium">Estimated Cost</span>
+            <span className="text-sm font-semibold">
+              {formatCost(span.tokenUsage!.cost)}
+            </span>
+          </div>
+        )}
+
+        {/* Inputs section */}
+        {hasInputs && (
+          <div className="mb-4">
+            <SectionHeader icon="ArrowRight" title="Input" />
+            <div className="mt-2">
+              <SimplifiedCodeTabComponent
+                language="json"
+                code={formatJsonData(span.inputs)}
+              />
+            </div>
+          </div>
+        )}
+
+        {/* Outputs section */}
+        {hasOutputs && (
+          <div className="mb-4">
+            <SectionHeader icon="ArrowLeft" title="Output" />
+            <div className="mt-2">
+              <SimplifiedCodeTabComponent
+                language="json"
+                code={formatJsonData(span.outputs)}
+              />
+            </div>
+          </div>
+        )}
+
+        {/* Empty state */}
+        {!hasInputs && !hasOutputs && !span.error && (
+          <div className="flex items-center justify-center py-8 text-muted-foreground">
+            <p className="text-sm">No additional details available</p>
+          </div>
+        )}
+      </div>
+    </div>
+  );
+}
+
+/**
+ * Metric card component for displaying key stats
+ */
+function MetricCard({
+  label,
+  value,
+  icon,
+}: {
+  label: string;
+  value: string;
+  icon: string;
+}) {
+  return (
+    <div className="rounded-md border border-border bg-background p-2">
+      <div className="flex items-center gap-1 text-xs text-muted-foreground">
+        <IconComponent name={icon} className="h-3 w-3" />
+        {label}
+      </div>
+      <div className="mt-0.5 text-sm font-semibold">{value}</div>
+    </div>
+  );
+}
+
+/**
+ * Section header with icon
+ */
+function SectionHeader({ icon, title }: { icon: string; title: string }) {
+  return (
+    <div className="flex items-center gap-2 text-sm font-medium">
+      <IconComponent name={icon} className="h-4 w-4 text-muted-foreground" />
+      {title}
+    </div>
+  );
+}
```

### `src/frontend/src/pages/FlowPage/components/LogsMainContent/index.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/FlowPage/components/LogsMainContent/index.tsx b/src/frontend/src/pages/FlowPage/components/LogsMainContent/index.tsx
new file mode 100644
index 0000000000..2b86e98f28
--- /dev/null
+++ b/src/frontend/src/pages/FlowPage/components/LogsMainContent/index.tsx
@@ -0,0 +1,105 @@
+import { useCallback, useEffect, useState } from "react";
+import { useGetTransactionsQuery } from "@/controllers/API/queries/transactions";
+import useFlowsManagerStore from "@/stores/flowsManagerStore";
+import { convertUTCToLocalTimezone } from "@/utils/utils";
+import { LogsTableView, type RunData } from "./components/LogsTableView";
+import { TracesDetailView } from "./components/TracesDetailView";
+
+type LogsTab = "logs" | "traces";
+
+interface LogsMainContentProps {
+  activeTab: LogsTab;
+  onTabChange: (tab: LogsTab) => void;
+  selectedRunId: string | null;
+  onSelectRun: (runId: string | null) => void;
+  selectedTraceId: string | null;
+}
+
+/**
+ * Main content area for logs - replaces the canvas when logs section is active
+ * - Logs tab: Shows table of all runs
+ * - Traces tab: Shows execution tree for selected run
+ */
+export default function LogsMainContent({
+  activeTab,
+  onTabChange,
+  selectedRunId,
+  onSelectRun,
+  selectedTraceId,
+}: LogsMainContentProps) {
+  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
+  const [pageIndex, setPageIndex] = useState(1);
+  const [pageSize] = useState(50);
+
+  // Fetch transactions/runs
+  const { data, isLoading, refetch } = useGetTransactionsQuery({
+    id: currentFlowId,
+    params: {
+      page: pageIndex,
+      size: pageSize,
+    },
+    mode: "union",
+  });
+
+  // Convert transactions to RunData format
+  const [runs, setRuns] = useState<RunData[]>([]);
+
+  useEffect(() => {
+    if (data?.rows) {
+      const convertedRuns: RunData[] = data.rows.map((row) => ({
+        id: row.id || row.vertex_id,
+        sessionId: row.flow_id || "default",
+        timestamp: convertUTCToLocalTimezone(row.timestamp),
+        input:
+          typeof row.inputs === "object"
+            ? JSON.stringify(row.inputs)
+            : String(row.inputs ?? ""),
+        output:
+          typeof row.outputs === "object"
+            ? JSON.stringify(row.outputs)
+            : String(row.outputs ?? ""),
+        status: row.status === "error" ? "error" : "success",
+        latencyMs: row.elapsed_time ? Math.round(row.elapsed_time * 1000) : 0,
+        error: row.error || undefined,
+      }));
+      setRuns(convertedRuns);
+    }
+  }, [data]);
+
+  const handleRefresh = useCallback(() => {
+    refetch();
+  }, [refetch]);
+
+  const handleViewTrace = useCallback(
+    (runId: string) => {
+      onSelectRun(runId);
+      onTabChange("traces");
+    },
+    [onSelectRun, onTabChange],
+  );
+
+  const handleLoadMore = useCallback(() => {
+    setPageIndex((prev) => prev + 1);
+  }, []);
+
+  const hasMore = data?.pagination
+    ? data.pagination.page < data.pagination.pages
+    : false;
+
+  return (
+    <div className="flex h-full w-full flex-col bg-background">
+      {activeTab === "logs" ? (
+        <LogsTableView
+          runs={runs}
+          isLoading={isLoading}
+          onViewTrace={handleViewTrace}
+          onRefresh={handleRefresh}
+          onLoadMore={handleLoadMore}
+          hasMore={hasMore}
+        />
+      ) : (
+        <TracesDetailView flowId={currentFlowId} initialRunId={selectedRunId} initialTraceId={selectedTraceId} />
+      )}
+    </div>
+  );
+}
```

### `src/frontend/src/pages/FlowPage/components/LogsMainContent/components/LogsTableView.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/FlowPage/components/LogsMainContent/components/LogsTableView.tsx b/src/frontend/src/pages/FlowPage/components/LogsMainContent/components/LogsTableView.tsx
new file mode 100644
index 0000000000..5d88c13d98
--- /dev/null
+++ b/src/frontend/src/pages/FlowPage/components/LogsMainContent/components/LogsTableView.tsx
@@ -0,0 +1,257 @@
+import { useMemo, useState } from "react";
+import IconComponent from "@/components/common/genericIconComponent";
+import { Badge } from "@/components/ui/badge";
+import { Button } from "@/components/ui/button";
+import { Loading } from "@/components/ui/loading";
+import {
+  Select,
+  SelectContent,
+  SelectItem,
+  SelectTrigger,
+  SelectValue,
+} from "@/components/ui/select";
+import {
+  Table,
+  TableBody,
+  TableCell,
+  TableHead,
+  TableHeader,
+  TableRow,
+} from "@/components/ui/table";
+import { cn } from "@/utils/utils";
+
+export interface RunData {
+  id: string;
+  sessionId: string;
+  timestamp: string;
+  input: string;
+  output: string;
+  status: "success" | "error";
+  latencyMs: number;
+  error?: string;
+}
+
+interface LogsTableViewProps {
+  runs: RunData[];
+  isLoading: boolean;
+  onViewTrace: (runId: string) => void;
+  onRefresh: () => void;
+  onLoadMore?: () => void;
+  hasMore?: boolean;
+}
+
+/**
+ * Format timestamp to readable string
+ */
+function formatTimestamp(timestamp: string): string {
+  const date = new Date(timestamp);
+  const now = new Date();
+  const isToday = date.toDateString() === now.toDateString();
+
+  if (isToday) {
+    return date.toLocaleTimeString(undefined, {
+      hour: "numeric",
+      minute: "2-digit",
+      hour12: true,
+    });
+  }
+
+  return date.toLocaleDateString(undefined, {
+    month: "short",
+    day: "numeric",
+    hour: "numeric",
+    minute: "2-digit",
+  });
+}
+
+/**
+ * Format latency
+ */
+function formatLatency(ms: number): string {
+  if (ms < 1000) return `${ms}ms`;
+  return `${(ms / 1000).toFixed(1)}s`;
+}
+
+/**
+ * Truncate text with ellipsis
+ */
+function truncateText(text: string, maxLength: number = 50): string {
+  if (!text) return "-";
+  if (text.length <= maxLength) return text;
+  return text.slice(0, maxLength) + "...";
+}
+
+/**
+ * Logs table view - flat list of all runs
+ */
+export function LogsTableView({
+  runs,
+  isLoading,
+  onViewTrace,
+  onRefresh,
+  onLoadMore,
+  hasMore,
+}: LogsTableViewProps) {
+  const [statusFilter, setStatusFilter] = useState<"all" | "success" | "error">(
+    "all",
+  );
+
+  // Filter and sort runs
+  const filteredRuns = useMemo(() => {
+    const filtered =
+      statusFilter === "all"
+        ? runs
+        : runs.filter((r) => r.status === statusFilter);
+
+    // Sort by timestamp (newest first)
+    return [...filtered].sort(
+      (a, b) =>
+        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
+    );
+  }, [runs, statusFilter]);
+
+  if (isLoading && runs.length === 0) {
+    return (
+      <div className="flex h-full items-center justify-center">
+        <div className="flex flex-col items-center gap-2 text-muted-foreground">
+          <Loading size={32} className="text-primary" />
+          <span className="text-sm">Loading runs...</span>
+        </div>
+      </div>
+    );
+  }
+
+  if (runs.length === 0) {
+    return (
+      <div className="flex h-full items-center justify-center">
+        <div className="flex flex-col items-center gap-3 text-muted-foreground">
+          <IconComponent name="ScrollText" className="h-12 w-12 opacity-50" />
+          <div className="text-center">
+            <p className="text-sm font-medium">No runs yet</p>
+            <p className="mt-1 text-xs">
+              Execute your flow to see run history here.
+            </p>
+          </div>
+        </div>
+      </div>
+    );
+  }
+
+  return (
+    <div className="flex h-full flex-col">
+      {/* Filter bar */}
+      <div className="flex items-center justify-between border-b border-border px-4 py-2">
+        <div className="flex items-center gap-2">
+          <Select
+            value={statusFilter}
+            onValueChange={(v) =>
+              setStatusFilter(v as "all" | "success" | "error")
+            }
+          >
+            <SelectTrigger className="h-8 w-[130px]">
+              <SelectValue />
+            </SelectTrigger>
+            <SelectContent>
+              <SelectItem value="all">All Status</SelectItem>
+              <SelectItem value="success">Success</SelectItem>
+              <SelectItem value="error">Errors</SelectItem>
+            </SelectContent>
+          </Select>
+          <span className="text-sm text-muted-foreground">
+            {filteredRuns.length} run{filteredRuns.length !== 1 ? "s" : ""}
+          </span>
+        </div>
+        <Button
+          variant="outline"
+          size="sm"
+          onClick={onRefresh}
+          disabled={isLoading}
+        >
+          <IconComponent
+            name="RefreshCw"
+            className={cn("mr-1.5 h-3.5 w-3.5", isLoading && "animate-spin")}
+          />
+          Refresh
+        </Button>
+      </div>
+
+      {/* Table */}
+      <div className="flex-1 overflow-auto">
+        <Table>
+          <TableHeader>
+            <TableRow>
+              <TableHead className="w-16">Status</TableHead>
+              <TableHead className="w-24">Run ID</TableHead>
+              <TableHead className="w-28">Time</TableHead>
+              <TableHead>Input</TableHead>
+              <TableHead>Output</TableHead>
+              <TableHead className="w-20">Latency</TableHead>
+              <TableHead className="w-24"></TableHead>
+            </TableRow>
+          </TableHeader>
+          <TableBody>
+            {filteredRuns.map((run) => (
+              <TableRow key={run.id} className="group">
+                <TableCell>
+                  <Badge
+                    variant={
+                      run.status === "success" ? "successStatic" : "errorStatic"
+                    }
+                    size="sm"
+                  >
+                    {run.status === "success" ? "OK" : "ERR"}
+                  </Badge>
+                </TableCell>
+                <TableCell className="font-mono text-xs text-muted-foreground">
+                  {run.id.slice(0, 8)}
+                </TableCell>
+                <TableCell className="text-sm text-muted-foreground">
+                  {formatTimestamp(run.timestamp)}
+                </TableCell>
+                <TableCell
+                  className="max-w-[200px] truncate text-sm"
+                  title={run.input}
+                >
+                  {truncateText(run.input, 50)}
+                </TableCell>
+                <TableCell
+                  className={cn(
+                    "max-w-[200px] truncate text-sm",
+                    run.error && "text-error-foreground",
+                  )}
+                  title={run.error || run.output}
+                >
+                  {run.error
+                    ? truncateText(run.error, 50)
+                    : truncateText(run.output, 50)}
+                </TableCell>
+                <TableCell className="text-sm text-muted-foreground">
+                  {formatLatency(run.latencyMs)}
+                </TableCell>
+                <TableCell>
+                  <Button
+                    variant="outline"
+                    size="sm"
+                    className="h-7 opacity-0 transition-opacity group-hover:opacity-100"
+                    onClick={() => onViewTrace(run.id)}
+                  >
+                    View Trace
+                  </Button>
+                </TableCell>
+              </TableRow>
+            ))}
+          </TableBody>
+        </Table>
+      </div>
+
+      {/* Load more */}
+      {hasMore && (
+        <div className="flex justify-center border-t border-border py-3">
+          <Button variant="outline" size="sm" onClick={onLoadMore}>
+            Load More
+          </Button>
+        </div>
+      )}
+    </div>
+  );
+}
```

### `src/frontend/src/pages/FlowPage/components/LogsMainContent/components/TracesDetailView.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/FlowPage/components/LogsMainContent/components/TracesDetailView.tsx b/src/frontend/src/pages/FlowPage/components/LogsMainContent/components/TracesDetailView.tsx
new file mode 100644
index 0000000000..f10a82bdab
--- /dev/null
+++ b/src/frontend/src/pages/FlowPage/components/LogsMainContent/components/TracesDetailView.tsx
@@ -0,0 +1,216 @@
+import { useMemo } from "react";
+import IconComponent from "@/components/common/genericIconComponent";
+import { Badge } from "@/components/ui/badge";
+import { Loading } from "@/components/ui/loading";
+import { useGetTransactionsQuery } from "@/controllers/API/queries/transactions";
+import { useGetTracesQuery } from "@/controllers/API/queries/traces";
+import useFlowsManagerStore from "@/stores/flowsManagerStore";
+import { convertUTCToLocalTimezone } from "@/utils/utils";
+import { TraceView } from "@/modals/flowLogsModal/components/TraceView";
+
+interface TracesDetailViewProps {
+  flowId: string;
+  initialRunId?: string | null;
+  initialTraceId?: string | null;
+}
+
+/**
+ * Format latency
+ */
+function formatLatency(ms: number): string {
+  if (ms < 1000) return `${ms}ms`;
+  return `${(ms / 1000).toFixed(1)}s`;
+}
+
+/**
+ * Format timestamp
+ */
+function formatTimestamp(timestamp: string): string {
+  const date = new Date(timestamp);
+  return date.toLocaleString(undefined, {
+    month: "short",
+    day: "numeric",
+    hour: "numeric",
+    minute: "2-digit",
+    second: "2-digit",
+    hour12: true,
+  });
+}
+
+/**
+ * Pretty print JSON
+ */
+function prettyJson(value: unknown): string {
+  if (value === null || value === undefined) return "-";
+  if (typeof value === "string") {
+    try {
+      const parsed = JSON.parse(value);
+      return JSON.stringify(parsed, null, 2);
+    } catch {
+      return value;
+    }
+  }
+  return JSON.stringify(value, null, 2);
+}
+
+/**
+ * Fallback view showing run details when traces aren't available
+ */
+function RunDetailsFallback({ runId }: { runId: string }) {
+  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
+
+  const { data: transactionsData, isLoading } = useGetTransactionsQuery({
+    id: currentFlowId,
+    params: { page: 1, size: 100 },
+    mode: "union",
+  });
+
+  const selectedRun = useMemo(() => {
+    if (!transactionsData?.rows || !runId) return null;
+    return transactionsData.rows.find(
+      (row) => (row.id || row.vertex_id) === runId,
+    );
+  }, [transactionsData, runId]);
+
+  if (isLoading) {
+    return (
+      <div className="flex h-full items-center justify-center">
+        <div className="flex flex-col items-center gap-2 text-muted-foreground">
+          <Loading size={32} className="text-primary" />
+          <span className="text-sm">Loading...</span>
+        </div>
+      </div>
+    );
+  }
+
+  if (!selectedRun) {
+    return (
+      <div className="flex h-full items-center justify-center">
+        <div className="flex flex-col items-center gap-3 text-muted-foreground">
+          <IconComponent name="AlertCircle" className="h-12 w-12 opacity-50" />
+          <div className="text-center">
+            <p className="text-sm font-medium">Run not found</p>
+          </div>
+        </div>
+      </div>
+    );
+  }
+
+  const isError = selectedRun.status === "error";
+  const latencyMs = selectedRun.elapsed_time
+    ? Math.round(selectedRun.elapsed_time * 1000)
+    : 0;
+
+  return (
+    <div className="flex h-full flex-col overflow-hidden">
+      <div className="border-b border-border px-6 py-4">
+        <div className="flex items-center gap-3">
+          <Badge variant={isError ? "errorStatic" : "successStatic"} size="sm">
+            {isError ? "ERROR" : "SUCCESS"}
+          </Badge>
+          <span className="font-mono text-sm text-muted-foreground">
+            {runId.slice(0, 8)}
+          </span>
+          <span className="text-sm text-muted-foreground">
+            {formatTimestamp(convertUTCToLocalTimezone(selectedRun.timestamp))}
+          </span>
+          <span className="text-sm text-muted-foreground">
+            {formatLatency(latencyMs)}
+          </span>
+        </div>
+      </div>
+
+      <div className="flex-1 overflow-auto p-6">
+        <div className="space-y-6">
+          <div>
+            <h3 className="mb-2 text-sm font-medium text-muted-foreground">Input</h3>
+            <pre className="overflow-auto rounded-md bg-muted/50 p-4 text-sm">
+              {prettyJson(selectedRun.inputs)}
+            </pre>
+          </div>
+
+          <div>
+            <h3 className="mb-2 text-sm font-medium text-muted-foreground">Output</h3>
+            <pre className="overflow-auto rounded-md bg-muted/50 p-4 text-sm">
+              {prettyJson(selectedRun.outputs)}
+            </pre>
+          </div>
+
+          {selectedRun.error && (
+            <div>
+              <h3 className="mb-2 text-sm font-medium text-error-foreground">Error</h3>
+              <pre className="overflow-auto rounded-md bg-error/10 p-4 text-sm text-error-foreground">
+                {selectedRun.error}
+              </pre>
+            </div>
+          )}
+        </div>
+      </div>
+    </div>
+  );
+}
+
+/**
+ * Traces detail view - shows execution tree with nested spans
+ * Falls back to simple run details if traces aren't available
+ */
+export function TracesDetailView({
+  flowId,
+  initialRunId,
+  initialTraceId,
+}: TracesDetailViewProps) {
+  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
+
+  // Check if traces API has data
+  const { data: tracesData, isLoading, isError } = useGetTracesQuery(
+    { flowId: currentFlowId ?? null, params: { page: 1, size: 10 } },
+    {
+      enabled: !!currentFlowId,
+      retry: 0, // Don't retry - backend has timeout handling
+      staleTime: 30000, // Consider data stale after 30s
+    },
+  );
+
+  const hasTraces = tracesData?.traces && tracesData.traces.length > 0;
+
+  // No run selected
+  if (!initialRunId && !initialTraceId) {
+    return (
+      <div className="flex h-full items-center justify-center">
+        <div className="flex flex-col items-center gap-3 text-muted-foreground">
+          <IconComponent name="Activity" className="h-12 w-12 opacity-50" />
+          <div className="text-center">
+            <p className="text-sm font-medium">Select a run</p>
+            <p className="mt-1 text-xs">
+              Choose a run from the sidebar to view details.
+            </p>
+          </div>
+        </div>
+      </div>
+    );
+  }
+
+  // Loading
+  if (isLoading) {
+    return (
+      <div className="flex h-full items-center justify-center">
+        <div className="flex flex-col items-center gap-2 text-muted-foreground">
+          <Loading size={32} className="text-primary" />
+          <span className="text-sm">Loading...</span>
+        </div>
+      </div>
+    );
+  }
+
+  // If traces available, show the TraceView with span tree
+  if (hasTraces && !isError) {
+    return (
+      <div className="h-full w-full">
+        <TraceView flowId={currentFlowId} initialTraceId={initialTraceId} />
+      </div>
+    );
+  }
+
+  // Fallback to simple run details
+  return <RunDetailsFallback runId={initialRunId} />;
+}
```

### `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/LogsSidebarGroup.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/LogsSidebarGroup.tsx b/src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/LogsSidebarGroup.tsx
new file mode 100644
index 0000000000..857fd0fde6
--- /dev/null
+++ b/src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/LogsSidebarGroup.tsx
@@ -0,0 +1,185 @@
+import { useEffect, useMemo } from "react";
+import IconComponent from "@/components/common/genericIconComponent";
+import { Badge } from "@/components/ui/badge";
+import { Loading } from "@/components/ui/loading";
+import {
+  SidebarGroup,
+  SidebarGroupContent,
+  SidebarGroupLabel,
+  SidebarMenu,
+  SidebarMenuItem,
+} from "@/components/ui/sidebar";
+import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
+import { useGetTracesQuery } from "@/controllers/API/queries/traces";
+import useFlowsManagerStore from "@/stores/flowsManagerStore";
+import { cn } from "@/utils/utils";
+
+type LogsTab = "logs" | "traces";
+
+interface LogsSidebarGroupProps {
+  activeTab: LogsTab;
+  onTabChange: (tab: LogsTab) => void;
+  selectedRunId: string | null;
+  onSelectRun: (runId: string | null) => void;
+  selectedTraceId: string | null;
+  onSelectTrace: (traceId: string | null) => void;
+}
+
+/**
+ * Format time for display
+ */
+function formatTime(timestamp: string): string {
+  const date = new Date(timestamp);
+  return date.toLocaleTimeString(undefined, {
+    hour: "numeric",
+    minute: "2-digit",
+    hour12: true,
+  });
+}
+
+/**
+ * Sidebar group for logs section
+ * - Logs tab: Just shows tabs (main content has the full table)
+ * - Traces tab: Shows tabs + run selector (to pick which run to view trace for)
+ */
+const LogsSidebarGroup = ({
+  activeTab,
+  onTabChange,
+  selectedRunId,
+  onSelectRun,
+  selectedTraceId,
+  onSelectTrace,
+}: LogsSidebarGroupProps) => {
+  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
+
+  // Fetch traces for Traces tab
+  const { data: tracesData, isLoading } = useGetTracesQuery(
+    { flowId: currentFlowId ?? null, params: { page: 1, size: 50 } },
+    { enabled: !!currentFlowId && activeTab === "traces" },
+  );
+
+  // Traces list (already sorted by backend - newest first)
+  const traces = useMemo(() => {
+    return tracesData?.traces ?? [];
+  }, [tracesData]);
+
+  // Auto-select first trace when switching to Traces tab
+  useEffect(() => {
+    if (activeTab === "traces" && traces.length > 0 && !selectedTraceId) {
+      onSelectTrace(traces[0].id);
+    }
+  }, [activeTab, traces, selectedTraceId, onSelectTrace]);
+
+  return (
+    <SidebarGroup className="flex h-full flex-col p-3 pr-2">
+      {/* Tabs */}
+      <SidebarGroupLabel className="mb-3 flex w-full cursor-default items-center justify-center">
+        <Tabs
+          value={activeTab}
+          onValueChange={(v) => onTabChange(v as LogsTab)}
+          className="w-full"
+        >
+          <TabsList className="w-full">
+            <TabsTrigger value="logs" className="flex-1">
+              Logs
+            </TabsTrigger>
+            <TabsTrigger value="traces" className="flex-1">
+              Traces
+            </TabsTrigger>
+          </TabsList>
+        </Tabs>
+      </SidebarGroupLabel>
+
+      <SidebarGroupContent className="flex-1 overflow-auto">
+        {activeTab === "logs" ? (
+          // Logs tab: Just show explanation - table is in main content
+          <div className="flex flex-col items-center justify-center py-8 text-center">
+            <IconComponent
+              name="ScrollText"
+              className="mb-2 h-8 w-8 text-muted-foreground opacity-50"
+            />
+            <p className="text-sm text-muted-foreground">
+              View all runs in the table
+            </p>
+            <p className="mt-1 text-xs text-muted-foreground">
+              Click a row to see its trace
+            </p>
+          </div>
+        ) : (
+          // Traces tab: Show trace selector
+          <>
+            <div className="mb-2 px-1 text-xs font-medium text-muted-foreground">
+              Select a run
+            </div>
+
+            {isLoading && (
+              <div className="flex items-center justify-center py-8">
+                <Loading size={20} className="text-muted-foreground" />
+              </div>
+            )}
+
+            {!isLoading && traces.length === 0 && (
+              <div className="flex flex-col items-center justify-center py-8 text-center">
+                <IconComponent
+                  name="Activity"
+                  className="mb-2 h-8 w-8 text-muted-foreground opacity-50"
+                />
+                <p className="text-sm text-muted-foreground">No traces yet</p>
+                <p className="mt-1 text-xs text-muted-foreground">
+                  Run your flow to see traces
+                </p>
+              </div>
+            )}
+
+            {!isLoading && traces.length > 0 && (
+              <SidebarMenu>
+                {traces.map((trace, idx) => {
+                  const isSelected = selectedTraceId === trace.id;
+                  return (
+                    <SidebarMenuItem key={trace.id}>
+                      <div
+                        className={cn(
+                          "flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors hover:bg-muted/50",
+                          isSelected && "bg-muted",
+                        )}
+                        onClick={() => onSelectTrace(trace.id)}
+                      >
+                        <Badge
+                          variant={
+                            trace.status === "error"
+                              ? "errorStatic"
+                              : "successStatic"
+                          }
+                          size="xq"
+                          className="h-5 w-5 shrink-0 p-0"
+                        >
+                          <IconComponent
+                            name={trace.status === "error" ? "X" : "Check"}
+                            className="h-3 w-3"
+                          />
+                        </Badge>
+                        <span className="flex-1 font-mono text-xs">
+                          {trace.id.slice(0, 8)}
+                        </span>
+                        <span className="text-xs text-muted-foreground">
+                          {formatTime(trace.startTime)}
+                        </span>
+                        {idx === 0 && (
+                          <Badge variant="outline" size="xq" className="ml-1">
+                            latest
+                          </Badge>
+                        )}
+                      </div>
+                    </SidebarMenuItem>
+                  );
+                })}
+              </SidebarMenu>
+            )}
+          </>
+        )}
+      </SidebarGroupContent>
+    </SidebarGroup>
+  );
+};
+
+export default LogsSidebarGroup;
```

### `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/MessagesSidebarGroup.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/MessagesSidebarGroup.tsx b/src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/MessagesSidebarGroup.tsx
new file mode 100644
index 0000000000..023a456bb9
--- /dev/null
+++ b/src/frontend/src/pages/FlowPage/components/flowSidebarComponent/components/MessagesSidebarGroup.tsx
@@ -0,0 +1,241 @@
+import { useCallback, useEffect, useMemo } from "react";
+import IconComponent from "@/components/common/genericIconComponent";
+import { Button } from "@/components/ui/button";
+import { Loading } from "@/components/ui/loading";
+import {
+  SidebarGroup,
+  SidebarGroupContent,
+  SidebarGroupLabel,
+  SidebarMenu,
+  SidebarMenuItem,
+  useSidebar,
+} from "@/components/ui/sidebar";
+import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
+import useFlowsManagerStore from "@/stores/flowsManagerStore";
+import { cn } from "@/utils/utils";
+
+interface MessagesSidebarGroupProps {
+  selectedSessionId: string | null;
+  onSelectSession: (id: string | null) => void;
+}
+
+interface SessionData {
+  id: string;
+  messageCount: number;
+  lastMessage: string;
+  lastTimestamp: string;
+}
+
+/**
+ * Empty state component when no sessions are available
+ */
+const SessionsEmptyState = () => {
+  return (
+    <div className="flex h-full min-h-[200px] w-full flex-col items-center justify-center px-4 py-8 text-center">
+      <IconComponent
+        name="MessagesSquare"
+        className="mb-3 h-10 w-10 text-muted-foreground opacity-50"
+      />
+      <p className="text-sm text-muted-foreground">No sessions yet</p>
+      <p className="mt-1 text-xs text-muted-foreground">
+        Run your flow to see sessions here
+      </p>
+    </div>
+  );
+};
+
+/**
+ * Loading state component
+ */
+const SessionsLoadingState = () => {
+  return (
+    <div className="flex h-full min-h-[100px] w-full items-center justify-center">
+      <Loading size={24} className="text-muted-foreground" />
+    </div>
+  );
+};
+
+/**
+ * Format timestamp to relative time
+ */
+const formatTimestamp = (timestamp: string) => {
+  if (!timestamp) return "";
+
+  try {
+    const date = new Date(timestamp);
+    if (isNaN(date.getTime())) return "";
+
+    const now = new Date();
+    const diff = now.getTime() - date.getTime();
+    const minutes = Math.floor(diff / 60000);
+    const hours = Math.floor(diff / 3600000);
+    const days = Math.floor(diff / 86400000);
+
+    if (minutes < 1) return "just now";
+    if (minutes < 60) return `${minutes}m ago`;
+    if (hours < 24) return `${hours}h ago`;
+    if (days < 7) return `${days}d ago`;
+    return date.toLocaleDateString();
+  } catch {
+    return "";
+  }
+};
+
+/**
+ * Truncate text to max length
+ */
+const truncateText = (text: string, maxLength: number = 20) => {
+  if (!text) return "";
+  if (text.length <= maxLength) return text;
+  return text.slice(0, maxLength) + "...";
+};
+
+/**
+ * Individual session item in the list
+ */
+const SessionListItem = ({
+  session,
+  isSelected,
+  onSelect,
+}: {
+  session: SessionData;
+  isSelected: boolean;
+  onSelect: () => void;
+}) => {
+  return (
+    <button
+      onClick={onSelect}
+      className={cn(
+        "flex w-full flex-col gap-1 rounded-md px-2 py-2 text-left transition-colors",
+        isSelected
+          ? "bg-accent text-accent-foreground"
+          : "hover:bg-accent/50 text-foreground",
+      )}
+    >
+      <div className="flex w-full items-center justify-between gap-2">
+        <span className="truncate text-xs font-medium">
+          {truncateText(session.id, 20) || "Default Session"}
+        </span>
+        <span className="shrink-0 text-[10px] text-muted-foreground">
+          {formatTimestamp(session.lastTimestamp)}
+        </span>
+      </div>
+      <div className="flex w-full items-center justify-between gap-2">
+        <span className="truncate text-xs text-muted-foreground">
+          {truncateText(session.lastMessage, 30)}
+        </span>
+        <span className="shrink-0 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
+          {session.messageCount}
+        </span>
+      </div>
+    </button>
+  );
+};
+
+/**
+ * Sidebar group for messages - shows list of sessions
+ * Each session can be selected to view its messages in the main content area
+ */
+const MessagesSidebarGroup = ({
+  selectedSessionId,
+  onSelectSession,
+}: MessagesSidebarGroupProps) => {
+  const { setActiveSection, open, toggleSidebar } = useSidebar();
+  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
+
+  // Fetch messages for the current flow
+  const { data: messagesData, isLoading } = useGetMessagesQuery(
+    { id: currentFlowId ?? undefined, mode: "union" },
+    { enabled: !!currentFlowId },
+  );
+
+  // Group messages by session_id
+  const sessions: SessionData[] = useMemo(() => {
+    const messages = (messagesData?.rows as any)?.data ?? [];
+    if (!messages.length) return [];
+
+    const sessionMap = new Map<string, any[]>();
+
+    messages.forEach((msg: any) => {
+      const sessionId = msg.session_id || "";
+      if (!sessionMap.has(sessionId)) {
+        sessionMap.set(sessionId, []);
+      }
+      sessionMap.get(sessionId)!.push(msg);
+    });
+
+    return Array.from(sessionMap.entries())
+      .map(([sessionId, msgs]) => {
+        // Sort messages by timestamp to get the latest
+        const sortedMsgs = [...msgs].sort(
+          (a, b) =>
+            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
+        );
+        const lastMsg = sortedMsgs[0];
+
+        return {
+          id: sessionId,
+          messageCount: msgs.length,
+          lastMessage: lastMsg?.text || "",
+          lastTimestamp: lastMsg?.timestamp || "",
+        };
+      })
+      .sort(
+        (a, b) =>
+          new Date(b.lastTimestamp).getTime() -
+          new Date(a.lastTimestamp).getTime(),
+      );
+  }, [messagesData]);
+
+  // Auto-select first session when data loads
+  useEffect(() => {
+    if (sessions.length > 0 && selectedSessionId === null) {
+      onSelectSession(sessions[0].id);
+    }
+  }, [sessions, selectedSessionId, onSelectSession]);
+
+  const handleClose = useCallback(() => {
+    setActiveSection("components");
+    if (!open) {
+      toggleSidebar();
+    }
+  }, [setActiveSection, open, toggleSidebar]);
+
+  const hasSessions = sessions.length > 0;
+
+  return (
+    <SidebarGroup className={`p-3 pr-2${!hasSessions ? " h-full" : ""}`}>
+      <SidebarGroupLabel className="flex w-full cursor-default items-center justify-between">
+        <span>Sessions</span>
+        <Button
+          variant="ghost"
+          size="icon"
+          onClick={handleClose}
+          className="h-6 w-6"
+          data-testid="close-messages-sidebar"
+        >
+          <IconComponent name="X" className="h-4 w-4" />
+        </Button>
+      </SidebarGroupLabel>
+      <SidebarGroupContent className="h-full overflow-y-auto">
+        {isLoading && <SessionsLoadingState />}
+        {!isLoading && !hasSessions && <SessionsEmptyState />}
+        {!isLoading && hasSessions && (
+          <SidebarMenu>
+            {sessions.map((session) => (
+              <SidebarMenuItem key={session.id || "default"}>
+                <SessionListItem
+                  session={session}
+                  isSelected={selectedSessionId === session.id}
+                  onSelect={() => onSelectSession(session.id)}
+                />
+              </SidebarMenuItem>
+            ))}
+          </SidebarMenu>
+        )}
+      </SidebarGroupContent>
+    </SidebarGroup>
+  );
+};
+
+export default MessagesSidebarGroup;
```

### `src/frontend/src/pages/FlowPage/components/MessagesMainContent/index.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/FlowPage/components/MessagesMainContent/index.tsx b/src/frontend/src/pages/FlowPage/components/MessagesMainContent/index.tsx
new file mode 100644
index 0000000000..4d51ecc78d
--- /dev/null
+++ b/src/frontend/src/pages/FlowPage/components/MessagesMainContent/index.tsx
@@ -0,0 +1,183 @@
+import { useIsFetching } from "@tanstack/react-query";
+import type { NewValueParams, SelectionChangedEvent } from "ag-grid-community";
+import cloneDeep from "lodash/cloneDeep";
+import { useMemo, useState } from "react";
+import IconComponent from "@/components/common/genericIconComponent";
+import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
+import Loading from "@/components/ui/loading";
+import {
+  useDeleteMessages,
+  useGetMessagesQuery,
+  useUpdateMessage,
+} from "@/controllers/API/queries/messages";
+import useAlertStore from "@/stores/alertStore";
+import useFlowsManagerStore from "@/stores/flowsManagerStore";
+import { useMessagesStore } from "@/stores/messagesStore";
+import { extractColumnsFromRows, messagesSorter } from "@/utils/utils";
+
+interface MessagesMainContentProps {
+  selectedSessionId?: string | null;
+}
+
+/**
+ * Main content area for messages - replaces the canvas when messages section is active
+ * Shows a table view of messages filtered by the selected session
+ */
+export default function MessagesMainContent({
+  selectedSessionId,
+}: MessagesMainContentProps) {
+  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
+  const setErrorData = useAlertStore((state) => state.setErrorData);
+  const setSuccessData = useAlertStore((state) => state.setSuccessData);
+  const messages = useMessagesStore((state) => state.messages);
+  const updateMessage = useMessagesStore((state) => state.updateMessage);
+  const deleteMessagesStore = useMessagesStore((state) => state.removeMessages);
+  const [selectedRows, setSelectedRows] = useState<string[]>([]);
+
+  // Fetch messages for the current flow
+  const { isLoading } = useGetMessagesQuery(
+    { id: currentFlowId ?? undefined, mode: "union" },
+    { enabled: !!currentFlowId },
+  );
+
+  const isFetching = useIsFetching({
+    queryKey: ["useGetMessagesQuery"],
+    exact: false,
+  });
+
+  const { mutate: deleteMessages } = useDeleteMessages({
+    onSuccess: () => {
+      deleteMessagesStore(selectedRows);
+      setSelectedRows([]);
+      setSuccessData({
+        title: "Messages deleted successfully.",
+      });
+    },
+    onError: () => {
+      setErrorData({
+        title: "Error deleting messages.",
+      });
+    },
+  });
+
+  const { mutate: updateMessageMutation } = useUpdateMessage();
+
+  function handleUpdateMessage(event: NewValueParams<any, string>) {
+    const newValue = event.newValue;
+    const field = event.column.getColId();
+    const row = cloneDeep(event.data);
+    const data = {
+      ...row,
+      [field]: newValue,
+    };
+    updateMessageMutation(
+      { message: data },
+      {
+        onSuccess: () => {
+          updateMessage(data);
+          setSuccessData({
+            title: "Message updated successfully.",
+          });
+        },
+        onError: () => {
+          setErrorData({
+            title: "Error updating message.",
+          });
+          event.data[field] = event.oldValue;
+          event.api.refreshCells();
+        },
+      },
+    );
+  }
+
+  // Filter messages by session
+  const filteredMessages = useMemo(() => {
+    let filtered = messages;
+
+    // Filter by flow_id
+    if (currentFlowId) {
+      filtered = filtered.filter((message) => message.flow_id === currentFlowId);
+    }
+
+    // Filter by session_id if selected
+    if (selectedSessionId !== null && selectedSessionId !== undefined) {
+      filtered = filtered.filter(
+        (message) => (message.session_id || "") === selectedSessionId,
+      );
+    }
+
+    return filtered;
+  }, [messages, currentFlowId, selectedSessionId]);
+
+  const columns = useMemo(() => {
+    return extractColumnsFromRows(filteredMessages, "intersection");
+  }, [filteredMessages]);
+
+  function handleRemoveMessages() {
+    deleteMessages({ ids: selectedRows });
+  }
+
+  const editable = useMemo(() => {
+    return [{ field: "text", onUpdate: handleUpdateMessage, editableCell: false }];
+  }, []);
+
+  const sessionLabel = selectedSessionId
+    ? selectedSessionId.length > 30
+      ? `${selectedSessionId.slice(0, 30)}...`
+      : selectedSessionId
+    : "All Sessions";
+
+  return (
+    <div className="flex h-full w-full flex-col bg-background">
+      {/* Header */}
+      <div className="flex items-center gap-2 border-b border-border px-4 py-2">
+        <IconComponent
+          name="MessagesSquare"
+          className="h-4 w-4 text-muted-foreground"
+        />
+        <span className="text-sm font-medium">Messages</span>
+        <span className="text-xs text-muted-foreground">
+          {sessionLabel} · {filteredMessages.length} message{filteredMessages.length !== 1 ? "s" : ""}
+        </span>
+      </div>
+
+      {/* Content */}
+      <div className="flex-1 overflow-hidden">
+        {isLoading || isFetching > 0 ? (
+          <div className="flex h-full w-full items-center justify-center">
+            <Loading />
+          </div>
+        ) : filteredMessages.length === 0 ? (
+          <div className="flex h-full w-full flex-col items-center justify-center text-center">
+            <IconComponent
+              name="MessagesSquare"
+              className="mb-3 h-12 w-12 text-muted-foreground opacity-50"
+            />
+            <p className="text-sm text-muted-foreground">No messages found</p>
+            <p className="mt-1 text-xs text-muted-foreground">
+              {selectedSessionId
+                ? "This session has no messages"
+                : "Run your flow to see messages here"}
+            </p>
+          </div>
+        ) : (
+          <TableComponent
+            key="messagesView"
+            onDelete={handleRemoveMessages}
+            readOnlyEdit
+            editable={editable}
+            overlayNoRowsTemplate="No data available"
+            onSelectionChanged={(event: SelectionChangedEvent) => {
+              setSelectedRows(event.api.getSelectedRows().map((row) => row.id));
+            }}
+            rowSelection="multiple"
+            suppressRowClickSelection={true}
+            pagination={true}
+            columnDefs={columns.sort(messagesSorter)}
+            rowData={filteredMessages}
+          />
+        )}
+      </div>
+    </div>
+  );
+}
```

### `src/frontend/src/modals/flowLogsModal/index.tsx` (modified)

```diff
diff --git a/src/frontend/src/modals/flowLogsModal/index.tsx b/src/frontend/src/modals/flowLogsModal/index.tsx
index 78ca6671b0..09dc841d14 100644
--- a/src/frontend/src/modals/flowLogsModal/index.tsx
+++ b/src/frontend/src/modals/flowLogsModal/index.tsx
@@ -4,12 +4,14 @@ import { useSearchParams } from "react-router-dom";
 import IconComponent from "@/components/common/genericIconComponent";
 import PaginatorComponent from "@/components/common/paginatorComponent";
 import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
+import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
 import { useGetTransactionsQuery } from "@/controllers/API/queries/transactions";
 import useFlowsManagerStore from "@/stores/flowsManagerStore";
 import type { TransactionLogsRow } from "@/types/api";
 import { convertUTCToLocalTimezone } from "@/utils/utils";
 import BaseModal from "../baseModal";
 import { LogDetailViewer } from "./components/LogDetailViewer";
+import { TraceView } from "./components/TraceView";
 import { createFlowLogsColumns } from "./config/flowLogsColumns";

 interface DetailViewState {
@@ -35,6 +37,7 @@ export default function FlowLogsModal({
     title: "",
     content: null,
   });
+  const [activeTab, setActiveTab] = useState<"logs" | "trace">("logs");
   const columns = createFlowLogsColumns();
   const flowIdFromUrl = searchParams.get("id");

@@ -90,58 +93,73 @@ export default function FlowLogsModal({
     }
   }, []);

-  const handleOpenAutoFocus = useCallback((e: Event) => {
-    const viewport = document.querySelector(
-      ".ag-body-viewport",
-    ) as HTMLElement | null;
-    if (viewport) {
-      e.preventDefault();
-      viewport.focus();
-    }
-    // If viewport doesn't exist (empty table), let default focus behavior happen
-  }, []);
-
   return (
     <>
-      <BaseModal
-        open={open}
-        setOpen={setOpen}
-        size="x-large"
-        onOpenAutoFocus={handleOpenAutoFocus}
-      >
+      <BaseModal open={open} setOpen={setOpen} size="x-large">
         <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
-        <BaseModal.Header description="Inspect component executions.">
-          <div className="flex w-full justify-between">
-            <div className="flex h-fit w-32 items-center">
+        <BaseModal.Header description="Inspect component executions and trace details.">
+          <div className="flex w-full items-center justify-between">
+            <div className="flex h-fit items-center">
               <span className="pr-2">Logs</span>
               <IconComponent name="ScrollText" className="mr-2 h-4 w-4" />
             </div>
-            <div className="flex h-fit w-32 items-center"></div>
+            <Tabs
+              value={activeTab}
+              onValueChange={(value) => setActiveTab(value as "logs" | "trace")}
+              className="flex flex-col self-center overflow-hidden rounded-md border bg-muted text-center"
+            >
+              <TabsList>
+                <TabsTrigger value="logs">Logs</TabsTrigger>
+                <TabsTrigger value="trace">Traces</TabsTrigger>
+              </TabsList>
+            </Tabs>
+            <div className="w-24"></div>
           </div>
         </BaseModal.Header>
-        <BaseModal.Content>
-          <TableComponent
-            key={"Executions"}
-            readOnlyEdit
-            className="h-max-full h-full w-full"
-            pagination={false}
-            columnDefs={columns}
-            autoSizeStrategy={{ type: "fitGridWidth" }}
-            rowData={rows}
-            headerHeight={rows.length === 0 ? 0 : undefined}
-            onCellClicked={handleCellClicked}
-          ></TableComponent>
-          {!isLoading && (data?.pagination.total ?? 0) >= 10 && (
-            <div className="flex justify-end px-3 py-4">
-              <PaginatorComponent
-                pageIndex={data?.pagination.page ?? 1}
-                pageSize={data?.pagination.size ?? 10}
-                rowsCount={[12, 24, 48, 96]}
-                totalRowsCount={data?.pagination.total ?? 0}
-                paginate={handlePageChange}
-                pages={data?.pagination.pages}
-              />
+        <BaseModal.Content overflowHidden>
+          {activeTab === "logs" ? (
+            <div className="flex h-full flex-col overflow-auto">
+              {rows.length === 0 ? (
+                <div className="flex h-full items-center justify-center">
+                  <div className="flex flex-col items-center gap-3 text-muted-foreground">
+                    <IconComponent name="ScrollText" className="h-12 w-12 opacity-50" />
+                    <div className="text-center">
+                      <p className="text-sm font-medium">No logs available</p>
+                      <p className="mt-1 text-xs">
+                        Run your flow to see component logs here.
+                      </p>
+                    </div>
+                  </div>
+                </div>
+              ) : (
+                <>
+                  <TableComponent
+                    key={"Executions"}
+                    readOnlyEdit
+                    className="h-max-full h-full w-full"
+                    pagination={false}
+                    columnDefs={columns}
+                    autoSizeStrategy={{ type: "fitGridWidth" }}
+                    rowData={rows}
+                    onCellClicked={handleCellClicked}
+                  />
+                  {!isLoading && (data?.pagination.total ?? 0) >= 10 && (
+                    <div className="flex justify-end px-3 py-4">
+                      <PaginatorComponent
+                        pageIndex={data?.pagination.page ?? 1}
+                        pageSize={data?.pagination.size ?? 10}
+                        rowsCount={[12, 24, 48, 96]}
+                        totalRowsCount={data?.pagination.total ?? 0}
+                        paginate={handlePageChange}
+                        pages={data?.pagination.pages}
+                      />
+                    </div>
+                  )}
+                </>
+              )}
             </div>
+          ) : (
+            <TraceView flowId={currentFlowId ?? flowIdFromUrl} />
           )}
         </BaseModal.Content>
       </BaseModal>
```

### `src/frontend/src/controllers/API/helpers/constants.ts` (modified - TRACES part)

```diff
diff --git a/src/frontend/src/controllers/API/helpers/constants.ts b/src/frontend/src/controllers/API/helpers/constants.ts
index 9c9532e455..e47e89302f 100644
--- a/src/frontend/src/controllers/API/helpers/constants.ts
+++ b/src/frontend/src/controllers/API/helpers/constants.ts
@@ -2,8 +2,11 @@ import { getBaseUrl } from "@/customization/utils/urls";
 import { BASE_URL_API_V2 } from "../../../constants/constants";

 export const URLs = {
+  TRACES: `traces`,
   TRANSACTIONS: `monitor/transactions`,
   API_KEY: `api_key`,
+  DATASETS: `datasets`,
+  EVALUATIONS: `evaluations`,
   FILES: `files`,
   FILE_MANAGEMENT: `files`,
   VERSION: `version`,
```

## Implementation Notes

1. **Trace type system**: The `Span` and `Trace` types in `types.ts` define a recursive tree structure where each `Span` can have `children: Span[]`. Span types include: chain, llm, tool, retriever, embedding, parser, agent.

2. **API layer**: Two React Query hooks are provided:
   - `useGetTracesQuery` - fetches a paginated list of traces for a flow, with optional session filtering.
   - `useGetTraceQuery` - fetches a single trace by ID with full span tree. Includes `convertSpan`/`convertTrace` functions to map API response types to frontend types.

3. **Dual rendering paths**: The `TracesDetailView` component checks if the traces API returns data. If traces are available, it renders the full `TraceView` with span tree. If not (e.g., the backend traces endpoint is not yet implemented), it falls back to `RunDetailsFallback` which shows simple input/output/error details from the transactions API.

4. **State coordination**: Logs/Messages state (selectedRunId, selectedTraceId, selectedSessionId, activeTab) is lifted up to `FlowPage/index.tsx` and passed down to both sidebar groups and main content areas, enabling the sidebar selection to drive what the main content displays.

5. **Constants registration**: The `TRACES` URL constant is added alongside `DATASETS` and `EVALUATIONS` in the API constants file.

6. **FlowLogsModal enhancement**: The existing modal now has a Logs/Traces tab. The Logs tab shows the existing AG Grid table with an improved empty state. The Traces tab renders the full `TraceView` component. The `overflowHidden` prop is passed to `BaseModal.Content` for proper scrolling behavior.
