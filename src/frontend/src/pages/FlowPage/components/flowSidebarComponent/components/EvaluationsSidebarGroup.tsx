import { useCallback, useEffect, useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useGetEvaluations } from "@/controllers/API/queries/evaluations/use-get-evaluations";
import type { EvaluationInfo } from "@/controllers/API/queries/evaluations/use-get-evaluations";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import CreateEvaluationModal from "@/modals/createEvaluationModal";

interface EvaluationsSidebarGroupProps {
  selectedEvaluationId: string | null;
  onSelectEvaluation: (id: string | null) => void;
}

/**
 * Empty state component when no evaluations are available
 */
const EvaluationsEmptyState = ({
  onCreateClick,
  canCreate,
}: {
  onCreateClick: () => void;
  canCreate: boolean;
}) => {
  return (
    <div className="flex h-full min-h-[200px] w-full flex-col items-center justify-center px-4 py-8 text-center">
      <IconComponent
        name="FlaskConical"
        className="mb-3 h-10 w-10 text-muted-foreground opacity-50"
      />
      <p className="text-sm text-muted-foreground">No evaluations yet</p>
      <p className="mt-1 text-xs text-muted-foreground">
        {canCreate
          ? "Run an evaluation to test your flow"
          : "Add Chat Input/Output to enable evaluations"}
      </p>
      {canCreate && (
        <Button
          variant="outline"
          size="sm"
          className="mt-3"
          onClick={onCreateClick}
        >
          <IconComponent name="Plus" className="mr-1 h-4 w-4" />
          New Evaluation
        </Button>
      )}
    </div>
  );
};

/**
 * Loading state component
 */
const EvaluationsLoadingState = () => {
  return (
    <div className="flex h-full min-h-[100px] w-full items-center justify-center">
      <IconComponent
        name="Loader2"
        className="h-6 w-6 animate-spin text-muted-foreground"
      />
    </div>
  );
};

/**
 * Format timestamp to relative time
 */
const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return "";

  try {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return "";

    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  } catch {
    return "";
  }
};

/**
 * Get status badge styling
 */
const getStatusStyles = (status: EvaluationInfo["status"]) => {
  switch (status) {
    case "completed":
      return "bg-success-background text-success";
    case "running":
      return "bg-warning-background text-warning";
    case "failed":
      return "bg-destructive/10 text-destructive";
    case "stopped":
      return "bg-amber-500/10 text-amber-500";
    default:
      return "bg-muted text-muted-foreground";
  }
};

/**
 * Individual evaluation item in the list
 */
const EvaluationListItem = ({
  evaluation,
  isSelected,
  onSelect,
}: {
  evaluation: EvaluationInfo;
  isSelected: boolean;
  onSelect: () => void;
}) => {
  const passRate =
    evaluation.total_items > 0
      ? Math.round((evaluation.passed_items / evaluation.total_items) * 100)
      : 0;

  return (
    <button
      onClick={onSelect}
      className={cn(
        "flex w-full flex-col gap-1 rounded-md px-2 py-2 text-left transition-colors",
        isSelected
          ? "bg-accent text-accent-foreground"
          : "hover:bg-accent/50 text-foreground",
      )}
    >
      <div className="flex w-full items-center justify-between gap-2">
        <span className="truncate text-xs font-medium">
          {evaluation.name || `Evaluation ${evaluation.id.slice(0, 8)}`}
        </span>
        <span
          className={cn(
            "shrink-0 rounded-full px-1.5 py-0.5 text-[10px]",
            getStatusStyles(evaluation.status),
          )}
        >
          {evaluation.status}
        </span>
      </div>
      <div className="flex w-full items-center justify-between gap-2">
        <span className="text-xs text-muted-foreground">
          {evaluation.dataset_name || "Dataset"}
        </span>
        <span className="shrink-0 text-[10px] text-muted-foreground">
          {formatTimestamp(evaluation.created_at)}
        </span>
      </div>
      {(evaluation.status === "completed" ||
        evaluation.status === "stopped") && (
        <div className="flex w-full items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">
            {evaluation.passed_items}/
            {evaluation.status === "stopped"
              ? evaluation.completed_items
              : evaluation.total_items}{" "}
            passed
          </span>
          <span
            className={cn(
              "text-xs font-medium",
              passRate >= 80
                ? "text-success"
                : passRate >= 50
                  ? "text-warning"
                  : "text-destructive",
            )}
          >
            {passRate}%
          </span>
        </div>
      )}
      {evaluation.status === "running" && (
        <div className="flex w-full items-center gap-2">
          <div className="h-1 flex-1 rounded-full bg-muted">
            <div
              className="h-1 rounded-full bg-primary transition-all"
              style={{
                width: `${(evaluation.completed_items / evaluation.total_items) * 100}%`,
              }}
            />
          </div>
          <span className="text-[10px] text-muted-foreground">
            {evaluation.completed_items}/{evaluation.total_items}
          </span>
        </div>
      )}
    </button>
  );
};

/**
 * Sidebar group for evaluations - shows list of evaluations for the current flow
 */
const EvaluationsSidebarGroup = ({
  selectedEvaluationId,
  onSelectEvaluation,
}: EvaluationsSidebarGroupProps) => {
  const { setActiveSection, open, toggleSidebar } = useSidebar();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const hasIO = useFlowStore((state) => state.hasIO);

  const [createModalOpen, setCreateModalOpen] = useState(false);

  // Fetch evaluations for the current flow
  const { data: evaluations, isLoading } = useGetEvaluations(
    { flowId: currentFlowId ?? undefined },
    { enabled: !!currentFlowId, refetchInterval: 5000 },
  );

  // Sort evaluations by date (newest first)
  const sortedEvaluations = useMemo(() => {
    if (!evaluations) return [];
    return [...evaluations].sort(
      (a, b) =>
        new Date(b.created_at || 0).getTime() -
        new Date(a.created_at || 0).getTime(),
    );
  }, [evaluations]);

  // Auto-select first evaluation when data loads
  useEffect(() => {
    if (sortedEvaluations.length > 0 && selectedEvaluationId === null) {
      onSelectEvaluation(sortedEvaluations[0].id);
    }
  }, [sortedEvaluations, selectedEvaluationId, onSelectEvaluation]);

  const handleClose = useCallback(() => {
    setActiveSection("components");
    if (!open) {
      toggleSidebar();
    }
  }, [setActiveSection, open, toggleSidebar]);

  const handleCreateSuccess = useCallback(
    (evaluationId: string) => {
      onSelectEvaluation(evaluationId);
    },
    [onSelectEvaluation],
  );

  const hasEvaluations = sortedEvaluations.length > 0;
  const canCreate = hasIO && !!currentFlowId;

  return (
    <>
      <SidebarGroup className={`p-3 pr-2${!hasEvaluations ? " h-full" : ""}`}>
        <SidebarGroupLabel className="flex w-full cursor-default items-center justify-between">
          <span>Evaluations</span>
          <div className="flex items-center gap-1">
            {canCreate && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setCreateModalOpen(true)}
                className="h-6 w-6"
                data-testid="new-evaluation-btn"
              >
                <IconComponent name="Plus" className="h-4 w-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={handleClose}
              className="h-6 w-6"
              data-testid="close-evaluations-sidebar"
            >
              <IconComponent name="X" className="h-4 w-4" />
            </Button>
          </div>
        </SidebarGroupLabel>
        <SidebarGroupContent className="h-full overflow-y-auto">
          {isLoading && <EvaluationsLoadingState />}
          {!isLoading && !hasEvaluations && (
            <EvaluationsEmptyState
              onCreateClick={() => setCreateModalOpen(true)}
              canCreate={canCreate}
            />
          )}
          {!isLoading && hasEvaluations && (
            <SidebarMenu>
              {sortedEvaluations.map((evaluation) => (
                <SidebarMenuItem key={evaluation.id}>
                  <EvaluationListItem
                    evaluation={evaluation}
                    isSelected={selectedEvaluationId === evaluation.id}
                    onSelect={() => onSelectEvaluation(evaluation.id)}
                  />
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          )}
        </SidebarGroupContent>
      </SidebarGroup>

      {currentFlow && (
        <CreateEvaluationModal
          open={createModalOpen}
          setOpen={setCreateModalOpen}
          flowId={currentFlow.id}
          flowName={currentFlow.name}
          onSuccess={handleCreateSuccess}
        />
      )}
    </>
  );
};

export default EvaluationsSidebarGroup;
