import type { ColDef } from "ag-grid-community";
import IconComponent from "@/components/common/genericIconComponent";
import { formatSmartTimestamp } from "@/utils/dateTime";

const formatObjectValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
};

const coerceNumber = (value: unknown): number | null => {
  if (value === null || value === undefined) return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const pickFirstNumber = (...candidates: unknown[]): number | null => {
  for (const candidate of candidates) {
    const num = coerceNumber(candidate);
    if (num !== null) return num;
  }
  return null;
};

const formatLatency = (latencyMs: number | null): string => {
  if (latencyMs === null) return "";
  if (!Number.isFinite(latencyMs)) return "";
  if (latencyMs < 1000) return `${Math.round(latencyMs)} ms`;
  return `${(latencyMs / 1000).toFixed(2)} s`;
};

const isNegativeStatus = (status: string): boolean => {
  const normalized = status.toLowerCase();
  return (
    normalized === "error" ||
    normalized === "failed" ||
    normalized.includes("fail") ||
    normalized.includes("error") ||
    normalized.includes("exception")
  );
};

const isPositiveStatus = (status: string): boolean => {
  const normalized = status.toLowerCase();
  return (
    normalized === "success" ||
    normalized === "completed" ||
    normalized === "ok" ||
    normalized.includes("success") ||
    normalized.includes("completed")
  );
};

const formatRunValue = (
  flowName: string | null | undefined,
  flowId: string | null | undefined,
): string => {
  const name = flowName ?? "";
  const id = flowId ?? "";
  if (!name && !id) return "";
  if (!name) return id;
  if (!id) return name;
  return `${name} - ${id}`;
};

export function createFlowTracesColumns({
  flowId,
  flowName,
}: {
  flowId?: string | null;
  flowName?: string | null;
} = {}): ColDef[] {
  return [
    {
      headerName: "Run",
      field: "run",
      flex: 1.0,
      minWidth: 240,
      filter: false,
      sortable: false,
      editable: false,
      valueGetter: () => formatRunValue(flowName, flowId),
    },
    {
      headerName: "Trace ID",
      field: "id",
      flex: 0.3,
      minWidth: 240,
      filter: false,
      sortable: false,
      editable: false,
    },

    {
      headerName: "Timestamp",
      field: "startTime",
      flex: 0.5,
      minWidth: 70,
      filter: false,
      sortable: false,
      editable: false,
      valueGetter: (params) => formatSmartTimestamp(params.data?.startTime),
    },
    {
      headerName: "Input",
      field: "input",
      flex: 1,
      minWidth: 150,
      filter: false,
      sortable: false,
      editable: false,
      valueGetter: (params) => formatObjectValue(params.data?.input),
    },
    {
      headerName: "Output",
      field: "output",
      flex: 1,
      minWidth: 150,
      filter: false,
      sortable: false,
      editable: false,
      valueGetter: (params) => formatObjectValue(params.data?.output),
    },
    {
      headerName: "Token",
      field: "totalTokens",
      flex: 0.5,
      minWidth: 50,
      filter: false,
      sortable: false,
      editable: false,
      valueGetter: (params) => {
        const tokens = pickFirstNumber(
          params.data?.totalTokens,
          params.data?.total_tokens,
        );
        return tokens === null ? "" : String(tokens);
      },
    },
    {
      headerName: "Latency",
      field: "totalLatencyMs",
      flex: 0.6,
      minWidth: 50,
      filter: false,
      sortable: false,
      editable: false,
      valueGetter: (params) => {
        const latencyMs = pickFirstNumber(
          params.data?.totalLatencyMs,
          params.data?.total_latency_ms,
        );
        return formatLatency(latencyMs);
      },
    },
    {
      headerName: "Status",
      field: "status",
      flex: 0.6,
      minWidth: 100,
      filter: false,
      sortable: false,
      editable: false,
      cellRenderer: (params: { value: string | null | undefined }) => {
        const status = params.value ?? "unknown";
        const negative = isNegativeStatus(status);
        const positive = !negative && isPositiveStatus(status);

        const colorClass = negative
          ? "text-status-red"
          : positive
            ? "text-status-green"
            : "text-muted-foreground";

        return (
          <div className="flex items-center">
            <IconComponent
              name="CircleCheck"
              className={`h-4 w-4 ${colorClass}`}
              aria-label={status}
              dataTestId={`flow-log-status-${status}`}
              skipFallback
            />
          </div>
        );
      },
    },
  ];
}
