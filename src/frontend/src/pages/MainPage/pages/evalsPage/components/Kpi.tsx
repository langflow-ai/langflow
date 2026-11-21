import type { ReactNode } from "react";

/** One headline number of a run or a comparison, with an optional line under it. */
export default function Kpi({
  label,
  value,
  hint,
  icon,
  testId,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  testId?: string;
}) {
  return (
    <div
      className="flex min-w-0 flex-col gap-1 rounded-lg border px-4 py-3"
      data-testid={testId}
    >
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {icon}
        {label}
      </span>
      <span className="truncate text-xl font-semibold tabular-nums">
        {value}
      </span>
      {hint && (
        <span className="flex min-w-0 items-center gap-1.5 truncate text-xs text-muted-foreground">
          {hint}
        </span>
      )}
    </div>
  );
}
