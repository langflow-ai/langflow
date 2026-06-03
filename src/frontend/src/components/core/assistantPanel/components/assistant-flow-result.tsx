import { ArrowRight, Check, GitBranch, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type {
  AgenticResult,
  CompactFlowNode,
} from "@/controllers/API/queries/agentic";
import CodeAreaModal from "@/modals/codeAreaModal";

const APPROVED_DISPLAY_DURATION_MS = 3000;
const MAX_VISIBLE_CHIPS = 6;

interface AssistantFlowResultProps {
  result: AgenticResult;
  onApproveFlow: () => boolean;
  onRegenerate?: () => void;
}

/** Colored chip for a single node type. */
function NodeChip({ type }: { type: string }) {
  return (
    <span className="rounded-md border border-violet-400/30 bg-violet-500/10 px-2 py-0.5 text-xs font-medium text-violet-300">
      {type}
    </span>
  );
}

/** Horizontal pipeline: NodeChip → NodeChip → ... → NodeChip */
function FlowPipeline({ nodes }: { nodes: CompactFlowNode[] }) {
  if (nodes.length === 0) return null;

  const visible = nodes.slice(0, MAX_VISIBLE_CHIPS);
  const truncated = nodes.length > MAX_VISIBLE_CHIPS;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {visible.map((node, idx) => (
        <span key={node.id} className="flex items-center gap-1.5">
          <NodeChip type={node.type} />
          {(idx < visible.length - 1 || truncated) && (
            <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground/50" />
          )}
        </span>
      ))}
      {truncated && (
        <span className="flex items-center gap-1.5">
          <span className="text-xs text-muted-foreground">
            +{nodes.length - MAX_VISIBLE_CHIPS} more
          </span>
        </span>
      )}
    </div>
  );
}

/** Key configured values per node, shown as small pills below the pipeline. */
function NodeValues({ nodes }: { nodes: CompactFlowNode[] }) {
  const configured = nodes.filter(
    (n) => n.values && Object.keys(n.values).length > 0,
  );
  if (configured.length === 0) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
      {configured.map((node) =>
        Object.entries(node.values!)
          .slice(0, 2)
          .map(([k, v]) => (
            <span
              key={`${node.id}-${k}`}
              className="text-[10px] text-muted-foreground"
            >
              <span className="font-medium text-muted-foreground/80">
                {node.type}
              </span>
              {" · "}
              {k}: <span className="text-foreground/70">{String(v)}</span>
            </span>
          )),
      )}
    </div>
  );
}

export function AssistantFlowResult({
  result,
  onApproveFlow,
  onRegenerate,
}: AssistantFlowResultProps) {
  const [showApproved, setShowApproved] = useState(false);
  const [isViewJsonOpen, setIsViewJsonOpen] = useState(false);

  const flowData = result.flowData;
  const nodes = flowData?.nodes ?? [];
  const edges = flowData?.edges ?? [];

  const nodeCount = result.nodeCount ?? nodes.length;
  const edgeCount = result.edgeCount ?? edges.length;

  const compactJson = useMemo(
    () => (flowData ? JSON.stringify(flowData, null, 2) : ""),
    [flowData],
  );

  useEffect(() => {
    if (showApproved) {
      const timer = setTimeout(
        () => setShowApproved(false),
        APPROVED_DISPLAY_DURATION_MS,
      );
      return () => clearTimeout(timer);
    }
  }, [showApproved]);

  const handleApprove = () => {
    const success = onApproveFlow();
    if (success) setShowApproved(true);
  };

  return (
    <div
      data-testid="assistant-flow-result"
      className="max-w-[85%] overflow-hidden rounded-xl border border-border bg-background"
    >
      {/* Header */}
      <div className="flex items-center gap-2.5 border-b border-border px-4 py-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-600">
          <GitBranch className="h-3.5 w-3.5 text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight text-foreground">
            Generated Flow
          </p>
          <p className="text-[10px] text-muted-foreground">
            {nodeCount} node{nodeCount !== 1 ? "s" : ""} · {edgeCount} edge
            {edgeCount !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {/* Pipeline */}
      {nodes.length > 0 && (
        <div className="px-4 py-3">
          <FlowPipeline nodes={nodes} />
          <NodeValues nodes={nodes} />
        </div>
      )}

      {/* Validation error (if any) */}
      {result.validationError && (
        <div className="mx-4 mb-3 rounded-md bg-destructive/5 px-3 py-2 text-xs text-destructive">
          {result.validationError}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 border-t border-border px-4 py-3">
        {showApproved ? (
          <div className="flex h-8 flex-1 items-center justify-center gap-1.5 rounded-lg bg-accent-emerald-foreground/10 text-sm font-medium text-accent-emerald-foreground">
            <Check className="h-4 w-4" />
            <span>Added to Canvas</span>
          </div>
        ) : (
          <button
            type="button"
            data-testid="assistant-approve-flow-button"
            className="h-8 flex-1 rounded-lg bg-violet-600 px-4 text-sm font-medium text-white transition-colors hover:bg-violet-500"
            onClick={handleApprove}
          >
            Add to Canvas
          </button>
        )}
        <button
          type="button"
          data-testid="assistant-view-json-button"
          className="h-8 rounded-lg border border-border px-3 text-xs font-medium text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground"
          onClick={() => setIsViewJsonOpen(true)}
        >
          JSON
        </button>
        {onRegenerate && (
          <button
            type="button"
            data-testid="assistant-regenerate-flow-button"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground"
            onClick={onRegenerate}
            title="Regenerate"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {compactJson && (
        <CodeAreaModal
          value={compactJson}
          setValue={() => {}}
          nodeClass={undefined}
          setNodeClass={() => {}}
          dynamic={false}
          readonly={true}
          open={isViewJsonOpen}
          setOpen={setIsViewJsonOpen}
          size="medium"
        >
          <></>
        </CodeAreaModal>
      )}
    </div>
  );
}
