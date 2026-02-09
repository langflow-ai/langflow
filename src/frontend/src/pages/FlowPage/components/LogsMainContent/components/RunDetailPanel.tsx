import IconComponent from "@/components/common/genericIconComponent";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { useGetTraceQuery } from "@/controllers/API/queries/traces";
import type { Span } from "@/modals/flowLogsModal/components/TraceView/types";

interface RunDetailPanelProps {
  traceId: string | null;
}

function formatJsonData(data: Record<string, unknown>): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

function extractIO(spans: Span[]): {
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
} {
  if (spans.length === 0) return { inputs: {}, outputs: {} };

  const root = spans[0];
  const hasRootInputs = Object.keys(root.inputs).length > 0;
  const hasRootOutputs = Object.keys(root.outputs).length > 0;

  if (hasRootInputs || hasRootOutputs) {
    return { inputs: root.inputs, outputs: root.outputs };
  }

  let inputs: Record<string, unknown> = {};
  let outputs: Record<string, unknown> = {};

  function walk(span: Span) {
    if (
      Object.keys(inputs).length === 0 &&
      Object.keys(span.inputs).length > 0
    ) {
      inputs = span.inputs;
    }
    if (
      Object.keys(outputs).length === 0 &&
      Object.keys(span.outputs).length > 0
    ) {
      outputs = span.outputs;
    }
    for (const child of span.children) {
      walk(child);
    }
  }

  for (const span of spans) {
    walk(span);
  }

  return { inputs, outputs };
}

function JsonSection({
  label,
  icon,
  data,
  emptyText,
}: {
  label: string;
  icon: string;
  data: Record<string, unknown>;
  emptyText: string;
}) {
  const hasData = Object.keys(data).length > 0;
  const json = hasData ? formatJsonData(data) : "";

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex h-9 shrink-0 items-center gap-1.5 px-4">
        <IconComponent name={icon} className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs font-semibold">{label}</span>
      </div>
      {hasData ? (
        <div className="min-h-0 flex-1 overflow-auto px-3 pb-3">
          <SimplifiedCodeTabComponent language="json" code={json} />
        </div>
      ) : (
        <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">
          {emptyText}
        </div>
      )}
    </div>
  );
}

export function RunDetailPanel({ traceId }: RunDetailPanelProps) {
  const { data: trace, isLoading } = useGetTraceQuery({
    traceId: traceId,
  });

  if (!traceId) {
    return (
      <div className="flex h-full items-center justify-center px-4 py-8">
        <div className="flex flex-col items-center text-muted-foreground">
          <IconComponent
            name="MousePointer"
            className="mb-3 h-10 w-10 opacity-50"
          />
          <p className="text-sm font-medium">Select a run</p>
          <p className="mt-1 text-xs">Click a run to view its input and output.</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center px-4 py-8">
        <div className="flex flex-col items-center gap-2 text-muted-foreground">
          <IconComponent name="Loader2" className="h-6 w-6 animate-spin" />
          <span className="text-xs">Loading trace...</span>
        </div>
      </div>
    );
  }

  if (!trace) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
        Trace not found
      </div>
    );
  }

  const { inputs, outputs } = extractIO(trace.spans);

  return (
    <div className="flex h-full w-full overflow-hidden">
      {/* Input — left half */}
      <div className="h-full w-1/2 overflow-hidden border-r border-border">
        <JsonSection label="Input" icon="LogIn" data={inputs} emptyText="No input data" />
      </div>
      {/* Output — right half */}
      <div className="h-full w-1/2 overflow-hidden">
        <JsonSection
          label="Output"
          icon="LogOut"
          data={outputs}
          emptyText="No output data"
        />
      </div>
    </div>
  );
}
