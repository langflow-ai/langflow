import { useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Loading from "@/components/ui/loading";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useGetEvaluation } from "@/controllers/API/queries/evaluations/use-get-evaluation";
import type { EvaluationInfo } from "@/controllers/API/queries/evaluations/use-get-evaluations";
import { useRunEvaluation } from "@/controllers/API/queries/evaluations/use-run-evaluation";
import useAlertStore from "@/stores/alertStore";

interface EvaluationsMainContentProps {
  selectedEvaluationId?: string | null;
}

const statusColors: Record<string, string> = {
  pending: "text-muted-foreground",
  running: "text-primary",
  completed: "text-emerald-600",
  failed: "text-destructive",
};

const formatDuration = (ms?: number) => {
  if (!ms) return "-";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
};

const formatRuntime = (ms?: number) => {
  if (!ms) return "-";
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes > 0)
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  return `${seconds}s`;
};

const formatTokens = (tokens?: number) => {
  if (!tokens) return "-";
  return tokens.toLocaleString();
};

/**
 * A cell that shows truncated text, expanding inline on click.
 */
const ExpandableCell = ({ text }: { text?: string | null }) => {
  const [expanded, setExpanded] = useState(false);

  if (!text) {
    return <span className="text-muted-foreground">-</span>;
  }

  return (
    <div
      className={
        expanded
          ? "max-w-96 cursor-pointer whitespace-pre-wrap break-words py-1 text-sm"
          : "max-w-48 cursor-pointer truncate"
      }
      onClick={() => setExpanded(!expanded)}
      title={expanded ? "Click to collapse" : "Click to expand"}
    >
      {text}
    </div>
  );
};

/**
 * Empty state when no evaluation is selected
 */
const NoEvaluationSelected = () => (
  <div className="flex h-full w-full flex-col items-center justify-center text-center">
    <IconComponent
      name="FlaskConical"
      className="mb-3 h-12 w-12 text-muted-foreground opacity-50"
    />
    <p className="text-sm text-muted-foreground">No evaluation selected</p>
    <p className="mt-1 text-xs text-muted-foreground">
      Select an evaluation from the sidebar to view results
    </p>
  </div>
);

/**
 * Main content area for evaluations - replaces the canvas when evaluations section is active
 * Uses the same UI as the standalone EvaluationPage
 */
export default function EvaluationsMainContent({
  selectedEvaluationId,
}: EvaluationsMainContentProps) {
  const { setErrorData, setSuccessData } = useAlertStore();

  const {
    data: evaluation,
    isLoading,
    refetch,
  } = useGetEvaluation(
    { evaluationId: selectedEvaluationId ?? "" },
    {
      enabled: !!selectedEvaluationId,
      refetchInterval: (query) => {
        const data = query.state.data as EvaluationInfo | undefined;
        return data?.status === "running" || data?.status === "pending"
          ? 2000
          : false;
      },
    },
  );

  const runEvaluationMutation = useRunEvaluation({
    onSuccess: () => {
      setSuccessData({ title: "Evaluation started" });
      refetch();
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to run evaluation",
        list: [error?.response?.data?.detail || error?.message],
      });
    },
  });

  // Interactive pass criteria — initialized from evaluation data
  const [localPassMetric, setLocalPassMetric] = useState<string | null>(null);
  const [localPassThreshold, setLocalPassThreshold] = useState(0.5);
  const [criteriaInitialized, setCriteriaInitialized] = useState<string | null>(null);

  // Sync local criteria when evaluation data loads / changes
  if (evaluation && criteriaInitialized !== evaluation.id) {
    setLocalPassMetric(evaluation.pass_metric ?? null);
    setLocalPassThreshold(evaluation.pass_threshold ?? 0.5);
    setCriteriaInitialized(evaluation.id);
  }

  // Recompute pass/fail per row based on local criteria
  const recomputedResults = useMemo(() => {
    if (!evaluation?.results) return [];
    return evaluation.results.map((r) => {
      let passed: boolean;
      if (
        localPassMetric &&
        localPassMetric in r.scores &&
        r.scores[localPassMetric] != null
      ) {
        passed = r.scores[localPassMetric] >= localPassThreshold;
      } else {
        const vals = Object.values(r.scores).filter(
          (s): s is number => s != null,
        );
        const avg = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
        passed = avg >= localPassThreshold;
      }
      return { ...r, passed };
    });
  }, [evaluation?.results, localPassMetric, localPassThreshold]);

  const recomputedPassCount = recomputedResults.filter((r) => r.passed).length;

  const handleReRun = () => {
    if (selectedEvaluationId) {
      runEvaluationMutation.mutate({ evaluationId: selectedEvaluationId });
    }
  };

  if (!selectedEvaluationId) {
    return <NoEvaluationSelected />;
  }

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loading size={64} className="text-primary" />
      </div>
    );
  }

  if (!evaluation) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center text-center">
        <IconComponent
          name="FlaskConical"
          className="mb-3 h-12 w-12 text-muted-foreground opacity-50"
        />
        <p className="text-sm text-muted-foreground">Evaluation not found</p>
      </div>
    );
  }

  const hasConversations = evaluation.results?.some((r) => r.conversation_id) ?? false;

  // Pre-compute message range each turn sees: "0" for first, "0-2", "0-4", etc.
  const msgRangeMap = new Map<string, string>();
  if (hasConversations && evaluation.results) {
    const convTurnCounters = new Map<string, number>();
    for (const result of evaluation.results) {
      const convId = result.conversation_id || "default";
      const turnNum = (convTurnCounters.get(convId) || 0) + 1;
      convTurnCounters.set(convId, turnNum);
      const lastIdx = (turnNum - 1) * 2;
      msgRangeMap.set(result.id, lastIdx === 0 ? "0" : `0-${lastIdx}`);
    }
  }

  const passRate =
    evaluation.total_items > 0
      ? ((recomputedPassCount / evaluation.total_items) * 100).toFixed(0)
      : "0";

  const totalCols =
    7 +
    evaluation.scoring_methods.length +
    (evaluation.scoring_methods.includes("llm_judge") ? 1 : 0) +
    (hasConversations ? 2 : 0);

  return (
    <div className="flex h-full w-full flex-col bg-muted/30">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-background px-6 py-3">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold">
            {evaluation.name || `Evaluation ${evaluation.id.slice(0, 8)}`}
          </h2>
          <span className="text-xs text-muted-foreground">&middot;</span>
          <span className={`text-xs capitalize ${statusColors[evaluation.status] ?? "text-muted-foreground"}`}>
            {evaluation.status}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleReRun}
          disabled={
            evaluation.status === "running" ||
            runEvaluationMutation.isPending
          }
        >
          <IconComponent name="Play" className="mr-1.5 h-3.5 w-3.5" />
          Re-run
        </Button>
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col gap-3 overflow-auto p-4">
        {/* Summary cards row */}
        <div className="flex items-stretch gap-3">
          {/* Metadata card */}
          <div className="flex items-center gap-6 rounded-lg border border-border bg-background px-5 py-3">
            <div className="flex flex-col items-center">
              <span className="text-[11px] text-muted-foreground">Dataset</span>
              <span className="flex items-center gap-1.5 text-sm font-semibold">
                <IconComponent name={hasConversations ? "MessagesSquare" : "TableProperties"} className="h-3.5 w-3.5 text-muted-foreground" />
                {evaluation.dataset_name}
              </span>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-[11px] text-muted-foreground">Items</span>
              <span className="text-sm font-semibold">{evaluation.total_items}</span>
            </div>
          </div>

          {/* Stats cards — only when completed */}
          {evaluation.status === "completed" && (
            <>
              <div className="flex items-center gap-6 rounded-lg border border-border bg-background px-5 py-3">
                <div className="flex flex-col items-center">
                  <span className="text-[11px] text-muted-foreground">Mean Duration</span>
                  <span className="text-sm font-semibold">{formatDuration(evaluation.mean_duration_ms)}</span>
                </div>
                <div className="flex flex-col items-center">
                  <span className="text-[11px] text-muted-foreground">Runtime</span>
                  <span className="text-sm font-semibold">{formatRuntime(evaluation.total_runtime_ms)}</span>
                </div>
              </div>
              {evaluation.total_flow_tokens != null && evaluation.total_flow_tokens > 0 && (
                <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-background px-5 py-3">
                  <span className="text-[11px] text-muted-foreground">Flow Tokens</span>
                  <span className="text-sm font-semibold">{evaluation.total_flow_tokens.toLocaleString()}</span>
                </div>
              )}
              {evaluation.total_llm_judge_tokens != null && evaluation.total_llm_judge_tokens > 0 && (
                <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-background px-5 py-3">
                  <span className="text-[11px] text-muted-foreground">Judge Tokens</span>
                  <span className="text-sm font-semibold">{evaluation.total_llm_judge_tokens.toLocaleString()}</span>
                </div>
              )}
              <div className="flex flex-col items-center justify-center rounded-lg border border-border bg-background px-5 py-3">
                <span className="text-[11px] text-muted-foreground">Pass Rate</span>
                <span className="text-sm font-semibold">
                  {passRate}%
                  <span className="ml-1 text-[11px] font-normal text-muted-foreground">
                    ({recomputedPassCount}/{evaluation.total_items})
                  </span>
                </span>
              </div>
            </>
          )}
        </div>

        {/* Progress bar for running evaluations */}
        {evaluation.status === "running" && (
          <div className="flex items-center gap-3 rounded-lg border border-border bg-background px-4 py-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-all"
                style={{
                  width: `${(evaluation.completed_items / evaluation.total_items) * 100}%`,
                }}
              />
            </div>
            <span className="text-xs text-muted-foreground">
              {evaluation.completed_items}/{evaluation.total_items}
            </span>
          </div>
        )}

        {/* Error message */}
        {evaluation.error_message && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3">
            <p className="text-xs text-destructive">{evaluation.error_message}</p>
          </div>
        )}

        {/* Table card */}
        <div className="flex flex-1 flex-col rounded-lg border border-border bg-background">
          {/* Table toolbar — pass criteria */}
          {evaluation.status === "completed" && (
            <div className="flex items-center gap-2.5 border-b border-border px-4 py-2">
              <span className="text-xs text-muted-foreground whitespace-nowrap">Pass when</span>
              <Select
                value={localPassMetric ?? "__average__"}
                onValueChange={(v) =>
                  setLocalPassMetric(v === "__average__" ? null : v)
                }
              >
                <SelectTrigger className="h-7 w-36 text-xs focus:ring-0 focus:ring-offset-0">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__average__">Average All</SelectItem>
                  {evaluation.scoring_methods.map((m) => (
                    <SelectItem key={m} value={m}>
                      {m.replace("_", " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <span className="text-xs text-muted-foreground">&ge;</span>
              <Input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={localPassThreshold}
                onChange={(e) =>
                  setLocalPassThreshold(
                    Math.min(1, Math.max(0, parseFloat(e.target.value) || 0)),
                  )
                }
                className="h-7 w-16 text-xs focus:ring-0 focus:ring-offset-0 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
            </div>
          )}

          {/* Table */}
          <div className="flex-1 overflow-auto">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-10 text-xs">#</TableHead>
                  {hasConversations && (
                    <>
                      <TableHead className="w-24 text-xs">Session</TableHead>
                      <TableHead className="w-16 text-xs">History</TableHead>
                    </>
                  )}
                  <TableHead className="text-xs">Input</TableHead>
                  <TableHead className="text-xs">Expected</TableHead>
                  <TableHead className="text-xs">Actual</TableHead>
                  <TableHead className="w-20 text-xs">Duration</TableHead>
                  <TableHead className="w-24 text-xs">Flow Tokens</TableHead>
                  {evaluation.scoring_methods.includes("llm_judge") && (
                    <TableHead className="w-24 text-xs">Judge Tokens</TableHead>
                  )}
                  {evaluation.scoring_methods.map((method) => (
                    <TableHead key={method} className="w-20 text-xs capitalize">
                      {method.replace("_", " ")}
                    </TableHead>
                  ))}
                  <TableHead className="w-16 text-xs">Result</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recomputedResults.length > 0 ? (
                  recomputedResults.map((result, idx) => {
                    const prevConvId = idx > 0 ? recomputedResults[idx - 1].conversation_id : null;
                    const isNewConversation = hasConversations && result.conversation_id !== prevConvId && idx > 0;
                    return (
                      <TableRow key={result.id} className={isNewConversation ? "border-t-2 border-border" : ""}>
                        <TableCell className="text-xs text-muted-foreground">{idx + 1}</TableCell>
                        {hasConversations && (
                          <>
                            <TableCell className="text-xs text-muted-foreground">
                              {result.conversation_id
                                ? result.conversation_id.length > 12
                                  ? `${result.conversation_id.slice(0, 12)}...`
                                  : result.conversation_id
                                : "-"}
                            </TableCell>
                            <TableCell className="font-mono text-xs text-muted-foreground">
                              {msgRangeMap.get(result.id) ?? "-"}
                            </TableCell>
                          </>
                        )}
                        <TableCell className="text-xs">
                          <ExpandableCell text={result.input} />
                        </TableCell>
                        <TableCell className="text-xs">
                          <ExpandableCell text={result.expected_output} />
                        </TableCell>
                        <TableCell className="text-xs">
                          <ExpandableCell text={result.actual_output} />
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">{formatDuration(result.duration_ms)}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">{formatTokens(result.flow_tokens)}</TableCell>
                        {evaluation.scoring_methods.includes("llm_judge") && (
                          <TableCell className="text-xs text-muted-foreground">{formatTokens(result.llm_judge_tokens)}</TableCell>
                        )}
                        {evaluation.scoring_methods.map((method) => (
                          <TableCell key={method} className="text-xs font-medium">
                            {result.scores[method] != null
                              ? result.scores[method].toFixed(2)
                              : result.error
                                ? <span className="text-destructive" title={result.error}>err</span>
                                : "-"}
                          </TableCell>
                        ))}
                        <TableCell>
                          <span className={`text-xs font-medium ${result.passed ? "text-emerald-600" : "text-destructive"}`}>
                            {result.passed ? "Pass" : "Fail"}
                          </span>
                        </TableCell>
                      </TableRow>
                    );
                  })
                ) : (
                  <TableRow>
                    <TableCell
                      colSpan={totalCols}
                      className="py-12 text-center text-xs text-muted-foreground"
                    >
                      {evaluation.status === "pending"
                        ? "Evaluation not started yet"
                        : evaluation.status === "running"
                          ? "Running evaluation..."
                          : "No results"}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>
    </div>
  );
}
