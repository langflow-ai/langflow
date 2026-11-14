import { useTranslation } from "react-i18next";
import { cn } from "@/utils/utils";

export type ResultFilterValue = "all" | "passed" | "failed" | "errored";
export const RESULT_FILTERS: ResultFilterValue[] = [
  "all",
  "passed",
  "failed",
  "errored",
];

interface ResultFilterProps {
  value: ResultFilterValue;
  counts: Record<ResultFilterValue, number>;
  onChange: (value: ResultFilterValue) => void;
}

/**
 * A filter is a set of toggle buttons, not tabs: there is no panel per option, so
 * tab semantics would point aria-controls at nothing. Styled like the segmented tabs.
 */
export default function ResultFilter({
  value,
  counts,
  onChange,
}: ResultFilterProps) {
  const { t } = useTranslation();
  return (
    <div
      role="group"
      aria-label={t("evals.results.filterLabel")}
      className="inline-flex h-9 w-fit items-center rounded-lg bg-muted p-1 text-muted-foreground"
    >
      {RESULT_FILTERS.map((name) => {
        const active = name === value;
        return (
          <button
            key={name}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(name)}
            data-testid={`results-filter-${name}`}
            className={cn(
              "inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active && "bg-background text-foreground shadow",
            )}
          >
            {t(`evals.results.filter.${name}`)}
            <span className="tabular-nums text-muted-foreground">
              {counts[name]}
            </span>
          </button>
        );
      })}
    </div>
  );
}
