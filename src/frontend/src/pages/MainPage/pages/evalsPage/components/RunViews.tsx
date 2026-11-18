import { useTranslation } from "react-i18next";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { EvaluationRun } from "@/controllers/API/queries/evals/types";
import ModelComparison from "./ModelComparison";
import RunResults from "./RunResults";
import RunsTable from "./RunsTable";
import VersionSwitcher from "./VersionSwitcher";

export const RUN_VIEWS = ["comparison", "results", "runs"] as const;
export type RunView = (typeof RUN_VIEWS)[number];

export function isRunView(value: string | null): value is RunView {
  return RUN_VIEWS.some((view) => view === value);
}

interface RunViewsProps {
  runs: EvaluationRun[];
  selectedRun: EvaluationRun | undefined;
  /** The selected run's comparison runs, oldest first; empty when it is not in one. */
  comparisonRuns: EvaluationRun[];
  view: RunView;
  onView: (view: RunView) => void;
  /** Open a run's results. */
  onOpenRun: (runId: string) => void;
}

/** One view at a time: every run of the evaluation, the selected run's results, or its comparison. */
export default function RunViews({
  runs,
  selectedRun,
  comparisonRuns,
  view,
  onView,
  onOpenRun,
}: RunViewsProps) {
  const { t } = useTranslation();
  const comparison = selectedRun?.config.comparison;
  return (
    <Tabs
      value={view}
      onValueChange={(next) => {
        if (isRunView(next)) onView(next);
      }}
    >
      <TabsList aria-label={t("evals.detail.tabsLabel")} className="w-fit">
        <TabsTrigger value="runs" data-testid="detail-tab-runs">
          {t("evals.detail.runs", { count: runs.length })}
        </TabsTrigger>
        <TabsTrigger value="results" data-testid="detail-tab-results">
          {t("evals.results.title")}
        </TabsTrigger>
        {comparison && (
          <TabsTrigger value="comparison" data-testid="detail-tab-comparison">
            {t("evals.detail.comparison")}
          </TabsTrigger>
        )}
      </TabsList>
      {comparison && (
        <TabsContent value="comparison" className="mt-6">
          <ModelComparison
            runs={comparisonRuns}
            comparisonId={comparison.id}
            selectedRunId={selectedRun?.id ?? null}
            onSelect={onOpenRun}
          />
        </TabsContent>
      )}
      <TabsContent value="results" className="mt-6 flex flex-col gap-4">
        {comparison && (
          <VersionSwitcher
            runs={comparisonRuns}
            selectedRunId={selectedRun?.id ?? null}
            onSelect={onOpenRun}
          />
        )}
        {selectedRun && <RunResults key={selectedRun.id} run={selectedRun} />}
      </TabsContent>
      <TabsContent value="runs" className="mt-6">
        <RunsTable
          runs={runs}
          selectedRunId={selectedRun?.id ?? null}
          onSelect={onOpenRun}
        />
      </TabsContent>
    </Tabs>
  );
}
