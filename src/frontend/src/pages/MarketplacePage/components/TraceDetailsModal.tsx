import React, { useEffect, useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getTraces } from "@/controllers/API/queries/observability";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

interface TraceDetailsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  traceId: string | null;
}

export default function TraceDetailsModal({
  open,
  onOpenChange,
  traceId,
}: TraceDetailsModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<any>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedNode, setSelectedNode] = useState<string>("root");

  useEffect(() => {
    if (!open || !traceId) return;
    setLoading(true);
    setError(null);
    setData(null);
    getTraces(traceId)
      .then((res) => setData(res))
      .catch((e: any) => setError(e?.message || "Failed to load trace details"))
      .finally(() => setLoading(false));
  }, [open, traceId]);

  const trace = data?.trace;

  // Inline, scoped styles to keep modal size fixed and enable internal scrolling
  const modalScopedStyles = `
    .trace-detail-modal {
      --modal-border: #e5e7eb;
      --muted-bg: #f9fafb;
    }
    /* Fit grid below header to avoid clipping bottom content */
    .trace-detail-modal .fixed-shell { height: calc(80vh - 64px); }
    .trace-detail-modal .left-pane, .trace-detail-modal .right-pane { height: 100%; min-height: 0; }
    .trace-detail-modal .boxed { border: 1px solid var(--modal-border); border-radius: 8px; background: #fff; }
    .trace-detail-modal .boxed-muted { border: 1px solid var(--modal-border); border-radius: 8px; background: var(--muted-bg); }
    .trace-detail-modal .scroll-y { overflow-y: auto; }
    .trace-detail-modal .node-row { display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; border-radius: 6px; cursor: pointer; }
    .trace-detail-modal .node-row:hover { background: var(--muted-bg); }
    .trace-detail-modal .node-row.active { background: var(--muted-bg); }
    .trace-detail-modal pre { white-space: pre-wrap; word-wrap: break-word; overflow-x: auto; }
  `;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* Fixed-size modal with internal scroll to avoid content-based resizing */}
      <DialogContent className="trace-detail-modal sm:max-w-[1200px] w-[95vw] h-[80vh] overflow-hidden">
        <style dangerouslySetInnerHTML={{ __html: modalScopedStyles }} />
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between w-full">
            <span className="text-[#350E84] text-[16px]">
              Trace Id {traceId}
            </span>
            {/* <div className="flex items-center gap-2">
              {traceId && (
                <span
                  className="text-sm truncate max-w-[280px] mr-10 text-[#731FE3]"
                  title={traceId}
                >
                  ID: {traceId}
                </span>
              )}
            </div> */}
          </DialogTitle>
        </DialogHeader>
        {trace && <HeaderMeta trace={trace} />}

        {/* Boxed two-column layout inside fixed modal */}
        <div className="grid grid-cols-12 fixed-shell">
          {/* Left: Search + Trace Breakdown */}
          <div className="col-span-4 flex flex-col left-pane">
            {/* <div className="boxed p-3 mb-3">
              <div className="text-sm font-medium mb-2">Search</div>
              <Input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search (type, title, ID)"
              />
            </div> */}
            <div className="p-3 border border-[#EFEFEF] flex-1 scroll-y">
              <h3 className="text-sm font-medium mb-2 text-[#444444]">
                Trace Breakdown
              </h3>

              <Input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search (type, title, ID)"
                icon="search"
                className="mb-3"
              />
              {loading && (
                <div className="py-2 text-sm text-muted-foreground">
                  Loading breakdown…
                </div>
              )}
              {error && (
                <div className="py-2 text-sm text-destructive">{error}</div>
              )}
              {!loading && !error && trace && (
                <TraceBreakdown
                  trace={trace}
                  searchTerm={searchTerm}
                  selectedNode={selectedNode}
                  onSelect={setSelectedNode}
                />
              )}
            </div>
          </div>

          {/* Right: Meta header + Tabs */}
          <div className="col-span-8 right-pane flex flex-col h-full border border-[#efefef] border-l-0 p-3">
            <h3 className="text-[16px] font-medium text-[#350E84]">
              Chat Input (ChatInput-cGagA)
            </h3>
            <p className="text-xs text-[#64616A] mt-0.5">
              {trace?.timestamp ? formatDate(trace.timestamp) : "-"}
            </p>
            {loading && (
              <div className="py-2 text-sm text-muted-foreground">
                Loading trace…
              </div>
            )}
            {error && (
              <div className="py-2 text-sm text-destructive">{error}</div>
            )}
            {!loading && !error && trace && (
              <TraceDetailsView
                data={data}
                selectedNode={selectedNode}
                onSelect={setSelectedNode}
              />
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function HeaderMeta({ trace }: { trace: any }) {
  const latency = formatDuration(trace?.latency_ms);
  const env = trace?.environment || "-";
  const cost = formatCost(trace?.total_cost);
  const duration_ms = trace?.latency_ms;
  const createdOn = trace?.timestamp ? formatDate(trace.timestamp) : "-";
  return (
    <div className="flex items-center justify-between">
      {/* <div className="text-xs text-muted-foreground">
        Created on: {createdOn}
      </div> */}
      <div className="flex gap-2 text-xs">
        <span className="px-2 py-1 rounded bg-[#F5F2FF] text-[#64616A] font-medium text-[10px]">
          Latency: {latency}
        </span>
        <span className="px-2 py-1 rounded bg-[#F5F2FF] text-[#64616A] font-medium text-[10px]">
          Env: {env}
        </span>
        <span className="px-2 py-1 rounded bg-[#F5F2FF] text-[#64616A] font-medium text-[10px]">
          Cost: {cost}
        </span>
        <span className="px-2 py-1 rounded bg-[#F5F2FF] text-[#64616A] font-medium text-[10px]">
          Duration: {duration_ms}
        </span>
      </div>
    </div>
  );
}

function TraceDetailsView({
  data,
  selectedNode,
  onSelect,
}: {
  data: any;
  selectedNode: string;
  onSelect: (id: string) => void;
}) {
  const trace = data.trace;
  const observations = trace.observations || [];
  const traceName = trace.name || trace.trace_id;

  const allNodes = useMemo(
    () => [
      { name: traceName, node_id: "root", duration_ms: trace.latency_ms },
      ...observations.map((obs: any) => ({
        name: obs.name,
        node_id: obs.observation_id,
        duration_ms: obs.duration_ms,
      })),
    ],
    [traceName, trace.latency_ms, observations]
  );

  const selectedObservation = useMemo(() => {
    if (selectedNode === "root") return null;
    return (
      observations.find((o: any) => o.observation_id === selectedNode) || null
    );
  }, [selectedNode, observations]);

  const inputs = useMemo(() => {
    if (selectedObservation) {
      return selectedObservation.input_data
        ? { [selectedObservation.name]: selectedObservation.input_data }
        : {};
    }
    return observations.reduce((acc: any, obs: any) => {
      if (obs.input_data && Object.keys(obs.input_data).length > 0) {
        acc[obs.name] = obs.input_data;
      }
      return acc;
    }, {});
  }, [selectedObservation, observations]);

  const outputs = useMemo(() => {
    if (selectedObservation) {
      return selectedObservation.output_data
        ? { [selectedObservation.name]: selectedObservation.output_data }
        : {};
    }
    return observations.reduce((acc: any, obs: any) => {
      if (obs.output_data && Object.keys(obs.output_data).length > 0) {
        acc[obs.name] = obs.output_data;
      }
      return acc;
    }, {});
  }, [selectedObservation, observations]);

  const attributes = useMemo(() => {
    if (selectedObservation) {
      return selectedObservation.metadata || {};
    }
    return {};
  }, [selectedObservation]);

  return (
    <div className="space-y-3">
      {/* Tabs align with Inputs/Outputs and Attributes like in test.tx */}
      <Tabs defaultValue="io" className="w-full">
        <TabsList className="mb-2 border-b gap-8">
          <TabsTrigger value="io">Inputs / Outputs</TabsTrigger>
          <TabsTrigger value="attr">Attributes</TabsTrigger>
        </TabsList>
        {/* Tab content uses the parent right-pane scroll; no inner scroll here */}
        <TabsContent
          value="io"
          className="space-y-3 overflow-y-auto max-h-[calc(100vh-390px)]"
        >
          <Accordion
            type="multiple"
            className="w-full space-y-3"
            defaultValue={["inputs"]}
          >
            {/* Inputs */}
            <AccordionItem
              value="inputs"
              className="border border-[#efefef] rounded bg-white"
            >
              <AccordionTrigger className="px-3 py-2 text-sm font-semibold text-[#64616A] hover:no-underline">
                Inputs
              </AccordionTrigger>
              <AccordionContent className="px-3 pb-3 pt-0">
                {renderSection(inputs)}
              </AccordionContent>
            </AccordionItem>

            {/* Outputs */}
            <AccordionItem
              value="outputs"
              className="border border-[#efefef] rounded bg-white"
            >
              <AccordionTrigger className="px-3 py-2 text-sm font-semibold text-[#64616A] hover:no-underline">
                Outputs
              </AccordionTrigger>
              <AccordionContent className="px-3 pb-3 pt-0">
                {renderSection(outputs)}
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </TabsContent>
        <TabsContent
          value="attr"
          className="space-y-3 overflow-y-auto max-h-[calc(100vh-390px)]"
        >
          <div className="border border-[#efefef] rounded bg-white px-3 py-2">
            <div className=" text-sm font-semibold text-[#64616A] mb-2">
              Attributes
            </div>
            {renderSection(attributes)}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function TraceBreakdown({
  trace,
  searchTerm,
  selectedNode,
  onSelect,
}: {
  trace: any;
  searchTerm: string;
  selectedNode: string;
  onSelect: (id: string) => void;
}) {
  const observations = trace?.observations || [];
  const traceName = trace?.name || trace?.trace_id;
  const nodes = [
    {
      name: traceName,
      node_id: "root",
      duration_ms: trace?.latency_ms,
      type: "trace",
    },
    ...observations.map((obs: any) => ({
      name: obs.name,
      node_id: obs.observation_id,
      duration_ms: obs.duration_ms,
      type: obs.type || obs?.metadata?.type || "observation",
    })),
  ];

  const q = searchTerm.trim().toLowerCase();
  const filtered = q
    ? nodes.filter(
        (n) =>
          (n.name || "").toLowerCase().includes(q) ||
          (n.node_id || "").toLowerCase().includes(q) ||
          (n.type || "").toLowerCase().includes(q)
      )
    : nodes;

  if (!filtered.length) {
    return (
      <div className="text-xs text-muted-foreground">No components match</div>
    );
  }

  // Render as a simple tree: root at top, one vertical line leading to children
  const root = filtered.find((n) => n.node_id === "root");
  const children = filtered.filter((n) => n.node_id !== "root");

  return (
    <div className="space-y-1">
      {root && (
        <div
          className={`node-row ${
            selectedNode === root.node_id ? "active" : ""
          }`}
          onClick={() => onSelect(root.node_id)}
          title={`${root.name} • ${root.type}`}
        >
          <span
            className="text-sm font-medium text-[#444444] truncate"
            title={root.name}
          >
            {root.name}
          </span>
          <span className="ml-2 text-[10px] font-medium text-[#64616A]">
            {formatDuration(root.duration_ms)}
          </span>
        </div>
      )}
      {children.length > 0 && (
        <div className="ml-3 pl-3 border-l space-y-1">
          {children.map((node) => (
            <div
              key={node.node_id}
              className={`node-row text-xs font-medium ${
                selectedNode === node.node_id
                  ? "bg-[#F5F2FF] text-[#731FE3]"
                  : "text-[#64616A]"
              }`}
              onClick={() => onSelect(node.node_id)}
              title={`${node.name} • ${node.type}`}
            >
              <span className="text-xs truncate" title={node.name}>
                {node.name}
              </span>
              <span className="ml-2 text-[10px] text-muted-foreground">
                {formatDuration(node.duration_ms)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Helpers
function formatDuration(ms?: number) {
  return ms ? `${(ms / 1000).toFixed(2)}s` : "-";
}
function formatCost(cost?: number) {
  return typeof cost === "number" ? `$${cost.toFixed(6)}` : "-";
}
function formatDate(date?: string) {
  return date ? new Date(date).toLocaleString() : "-";
}
function recursiveJsonParse(data: any): any {
  if (typeof data === "string") {
    try {
      const parsed = JSON.parse(data);
      return recursiveJsonParse(parsed);
    } catch (e) {
      return data;
    }
  } else if (Array.isArray(data)) {
    return data.map((item) => recursiveJsonParse(item));
  } else if (typeof data === "object" && data !== null) {
    const newObj: { [key: string]: any } = {};
    for (const key in data) {
      if (Object.prototype.hasOwnProperty.call(data, key)) {
        newObj[key] = recursiveJsonParse(data[key]);
      }
    }
    return newObj;
  }
  return data;
}
function renderSection(obj: any) {
  if (!obj || typeof obj !== "object" || Object.keys(obj).length === 0) {
    return (
      <div className="p-2">
        <p className="text-xs text-[#64616A] opacity-60">No data</p>
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {Object.entries(obj).map(([k, v]) => {
        const formatted = recursiveJsonParse(v);
        const display =
          typeof formatted === "string"
            ? formatted
            : JSON.stringify(formatted, null, 2);
        return (
          <div
            key={k}
            className="border border-[#E7ECF4] bg-[#FBFAFF] rounded p-2"
          >
            <div className="text-sm font-medium mb-2 text-[#444444]">{k}</div>
            <pre className="text-sm whitespace-pre-wrap font-sans overflow-x-auto !font-regular !text-[#64616A] !bg-transparent">
              {String(display)}
            </pre>
          </div>
        );
      })}
    </div>
  );
}
