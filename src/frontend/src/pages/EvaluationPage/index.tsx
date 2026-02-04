import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { useGetEvaluation } from "@/controllers/API/queries/evaluations/use-get-evaluation";
import { useRunEvaluation } from "@/controllers/API/queries/evaluations/use-run-evaluation";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAlertStore from "@/stores/alertStore";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import PageLayout from "@/components/common/pageLayout";
import LoadingComponent from "@/components/ui/loading";

const getStatusBadge = (status: string) => {
  const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
    pending: "secondary",
    running: "default",
    completed: "outline",
    failed: "destructive",
  };
  return <Badge variant={variants[status] || "secondary"}>{status}</Badge>;
};

const formatDuration = (ms?: number) => {
  if (!ms) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
};

const formatRuntime = (ms?: number) => {
  if (!ms) return "-";
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes > 0) return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  return `${seconds}s`;
};

export default function EvaluationPage() {
  const { evaluationId } = useParams();
  const navigate = useCustomNavigate();
  const { setErrorData, setSuccessData } = useAlertStore();

  const {
    data: evaluation,
    isLoading,
    refetch,
  } = useGetEvaluation(
    { evaluationId: evaluationId! },
    {
      enabled: !!evaluationId,
      refetchInterval: (data) =>
        data?.status === "running" || data?.status === "pending" ? 2000 : false,
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

  const handleReRun = () => {
    if (evaluationId) {
      runEvaluationMutation.mutate({ evaluationId });
    }
  };

  if (isLoading) {
    return (
      <PageLayout
        title="Evaluation Results"
        backTo="/"
      >
        <div className="flex h-64 items-center justify-center">
          <LoadingComponent remSize={24} />
        </div>
      </PageLayout>
    );
  }

  if (!evaluation) {
    return (
      <PageLayout
        title="Evaluation Results"
        backTo="/"
      >
        <div className="flex h-64 items-center justify-center">
          <p className="text-muted-foreground">Evaluation not found</p>
        </div>
      </PageLayout>
    );
  }

  const passRate =
    evaluation.total_items > 0
      ? ((evaluation.passed_items / evaluation.total_items) * 100).toFixed(0)
      : "0";

  return (
    <PageLayout
      title="Evaluation Results"
      description={evaluation.name || `Evaluation ${evaluation.created_at}`}
      backTo="/"
    >
      <div className="flex flex-col gap-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {getStatusBadge(evaluation.status)}
            <span className="text-sm text-muted-foreground">
              Dataset: <strong>{evaluation.dataset_name}</strong>
            </span>
            <span className="text-sm text-muted-foreground">
              Flow: <strong>{evaluation.flow_name}</strong>
            </span>
            <span className="text-sm text-muted-foreground">
              Items: <strong>{evaluation.total_items}</strong>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleReRun}
              disabled={
                evaluation.status === "running" ||
                runEvaluationMutation.isPending
              }
            >
              <ForwardedIconComponent name="Play" className="mr-2 h-4 w-4" />
              Re-run
            </Button>
          </div>
        </div>

        {/* Progress bar for running evaluations */}
        {evaluation.status === "running" && (
          <div className="flex items-center gap-4">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-all"
                style={{
                  width: `${(evaluation.completed_items / evaluation.total_items) * 100}%`,
                }}
              />
            </div>
            <span className="text-sm text-muted-foreground">
              {evaluation.completed_items} / {evaluation.total_items}
            </span>
          </div>
        )}

        {/* Results Table */}
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">#</TableHead>
                <TableHead>Input</TableHead>
                <TableHead>Expected Output</TableHead>
                <TableHead>Actual Output</TableHead>
                <TableHead className="w-24">Duration</TableHead>
                <TableHead className="w-20">Passed</TableHead>
                {evaluation.scoring_methods.map((method) => (
                  <TableHead key={method} className="w-24">
                    {method.replace("_", " ")}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {evaluation.results && evaluation.results.length > 0 ? (
                evaluation.results.map((result, idx) => (
                  <TableRow key={result.id}>
                    <TableCell>{idx + 1}</TableCell>
                    <TableCell className="max-w-48 truncate">
                      {result.input}
                    </TableCell>
                    <TableCell className="max-w-48 truncate">
                      {result.expected_output}
                    </TableCell>
                    <TableCell className="max-w-48 truncate">
                      {result.actual_output || (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>{formatDuration(result.duration_ms)}</TableCell>
                    <TableCell>
                      <Badge
                        variant={result.passed ? "outline" : "destructive"}
                      >
                        {result.passed ? "true" : "false"}
                      </Badge>
                    </TableCell>
                    {evaluation.scoring_methods.map((method) => (
                      <TableCell key={method}>
                        {result.scores[method]?.toFixed(2) || "-"}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={6 + evaluation.scoring_methods.length}
                    className="text-center text-muted-foreground"
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

        {/* Summary Footer */}
        {evaluation.status === "completed" && (
          <div className="flex items-center gap-6 text-sm text-muted-foreground">
            <span>
              Pass Rate:{" "}
              <strong>
                {passRate}% ({evaluation.mean_score?.toFixed(2) || "0.00"} avg
                score)
              </strong>
            </span>
            <span>
              Mean Duration:{" "}
              <strong>{formatDuration(evaluation.mean_duration_ms)}</strong>
            </span>
            <span>
              Runtime:{" "}
              <strong>{formatRuntime(evaluation.total_runtime_ms)}</strong>
            </span>
          </div>
        )}

        {/* Error message */}
        {evaluation.error_message && (
          <div className="rounded-md border border-destructive bg-destructive/10 p-4">
            <p className="text-sm text-destructive">{evaluation.error_message}</p>
          </div>
        )}
      </div>
    </PageLayout>
  );
}
