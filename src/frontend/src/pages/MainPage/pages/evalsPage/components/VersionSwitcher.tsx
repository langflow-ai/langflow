import { useTranslation } from "react-i18next";
import type { EvaluationRun } from "@/controllers/API/queries/evals/types";
import { cn } from "@/utils/utils";
import VariantLabel from "./VariantLabel";

/** Switch the results between a comparison's versions without going back to the runs list. */
export default function VersionSwitcher({
  runs,
  selectedRunId,
  onSelect,
}: {
  /** The comparison's runs, oldest first. */
  runs: readonly EvaluationRun[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
}) {
  const { t } = useTranslation();
  const versions = runs.filter((run) => run.config.comparison);
  if (versions.length < 2) return null;
  return (
    <div
      role="group"
      aria-label={t("evals.compare.versionSwitcher")}
      className="flex flex-wrap gap-2"
      data-testid="version-switcher"
    >
      {versions.map((run) => {
        const comparison = run.config.comparison;
        if (!comparison) return null;
        const pressed = run.id === selectedRunId;
        return (
          <button
            key={run.id}
            type="button"
            aria-pressed={pressed}
            onClick={() => onSelect(run.id)}
            className={cn(
              "rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              pressed && "border-foreground bg-muted",
            )}
          >
            <VariantLabel
              index={comparison.index}
              overrides={comparison.variants[comparison.index] ?? []}
              detail={false}
            />
          </button>
        );
      })}
    </div>
  );
}
