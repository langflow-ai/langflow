import type { ColDef } from "ag-grid-community";
import IconComponent from "@/components/common/genericIconComponent";
import { formatSmartTimestamp } from "@/utils/dateTime";
import { formatTotalLatency, getStatusIconProps } from "../traceViewHelpers";
import {
  formatObjectValue,
  formatRunValue,
  pickFirstNumber,
} from "./flowTraceColumnsHelpers";

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
      headerName: "Timestamp (UTC)",
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
        return formatTotalLatency(latencyMs);
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
        const { colorClass, iconName, shouldSpin } = getStatusIconProps(status);

        return (
          <div className="flex items-center">
            <IconComponent
              name={iconName}
              className={`h-4 w-4 ${colorClass} ${shouldSpin ? "animate-spin" : ""}`}
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
