import { NEXT_VARIANT_GRACE_MS } from "@/controllers/API/queries/evals/polling";
import {
  type EvaluationRun,
  type ModelOverride,
  type RunStatus,
  type SafetySummary,
  TERMINAL_RUN_STATUSES,
} from "@/controllers/API/queries/evals/types";

/** A variant's place in the comparison: its run's status, or no run yet (waiting) or ever (not run). */
export type VariantState = RunStatus | "waiting" | "not_run";

export interface ComparisonEntry {
  index: number;
  overrides: ModelOverride[];
  run: EvaluationRun | null;
  state: VariantState;
  total: number;
  completed: number;
  passed: number;
  decided: number;
  errored: number;
  passRate: number | null;
  /** 95% Wilson interval of the pass rate; how far the rate could move with more rows. */
  interval: readonly [number, number] | null;
  cost: number | null;
  costPerRow: number | null;
  p50: number | null;
  p90: number | null;
  /** The judge's safety rates for this variant, when the evaluation asked for safety checks. */
  safety: SafetySummary | null;
  rank: number | null;
  /** The same pass rate as the top variant: only cost, then speed, put it below. */
  matchesTop: boolean;
  /** A lower pass rate, but within the top variant's margin of error: the data cannot tell the two apart. */
  tiedWithTop: boolean;
}

export interface Comparison {
  id: string;
  /** In plan order, the order the user set the versions in. */
  entries: ComparisonEntry[];
  /** Ranked variants, best first; unfinished ones are left out. */
  ranked: ComparisonEntry[];
  mostAccurate: ComparisonEntry | null;
  cheapest: ComparisonEntry | null;
  fastest: ComparisonEntry | null;
  totalCost: number | null;
  finished: number;
}

const Z_95 = 1.96;
const RANKED_STATUSES: ReadonlySet<VariantState> = new Set([
  "completed",
  "failed",
]);

export function wilsonInterval(
  passed: number,
  decided: number,
  z: number = Z_95,
): readonly [number, number] | null {
  if (decided <= 0) return null;
  const rate = passed / decided;
  const z2 = z * z;
  const centre = (rate + z2 / (2 * decided)) / (1 + z2 / decided);
  const half =
    (z / (1 + z2 / decided)) *
    Math.sqrt((rate * (1 - rate)) / decided + z2 / (4 * decided * decided));
  return [Math.max(0, centre - half), Math.min(1, centre + half)];
}

/** The model names a variant runs, in override order; empty when it runs the flow's own models. */
export function variantModels(overrides: readonly ModelOverride[]): string[] {
  return [
    ...new Set(overrides.map((override) => override.value[0]?.name ?? "")),
  ].filter(Boolean);
}

export function variantProviders(
  overrides: readonly ModelOverride[],
): string[] {
  return [
    ...new Set(overrides.map((override) => override.value[0]?.provider ?? "")),
  ].filter(Boolean);
}

function entryOf(
  index: number,
  overrides: ModelOverride[],
  run: EvaluationRun | null,
  missing: VariantState,
): ComparisonEntry {
  const summary = run?.summary;
  const decided = summary?.rows.decided ?? 0;
  const passed = run?.passed_items ?? 0;
  const completed = run?.completed_items ?? 0;
  const cost = summary?.cost_usd.complete ? summary.cost_usd.total : null;
  return {
    index,
    overrides,
    run,
    state: run?.status ?? missing,
    total: run?.total_items ?? 0,
    completed,
    passed,
    decided,
    errored: run?.failed_items ?? 0,
    passRate: summary?.pass_rate ?? null,
    interval: wilsonInterval(passed, decided),
    cost,
    costPerRow: cost !== null && completed > 0 ? cost / completed : null,
    p50: summary?.duration_ms.p50 ?? null,
    p90: summary?.duration_ms.p90 ?? null,
    // One judge carries the safety checks, as on a single run's results.
    safety: Object.values(summary?.safety ?? {})[0] ?? null,
    rank: null,
    matchesTop: false,
    tiedWithTop: false,
  };
}

const valueOr = (value: number | null, fallback: number) => value ?? fallback;

/** Best pass rate first, then the cheaper, then the faster; unknown cost or speed sorts last. */
function compareEntries(a: ComparisonEntry, b: ComparisonEntry): number {
  return (
    valueOr(b.passRate, -1) - valueOr(a.passRate, -1) ||
    valueOr(a.cost, Number.POSITIVE_INFINITY) -
      valueOr(b.cost, Number.POSITIVE_INFINITY) ||
    valueOr(a.p50, Number.POSITIVE_INFINITY) -
      valueOr(b.p50, Number.POSITIVE_INFINITY) ||
    a.index - b.index
  );
}

function lowest(
  entries: ComparisonEntry[],
  value: (entry: ComparisonEntry) => number | null,
): ComparisonEntry | null {
  let best: ComparisonEntry | null = null;
  for (const entry of entries) {
    const current = value(entry);
    if (current === null) continue;
    const bestValue = best ? value(best) : null;
    if (bestValue === null || current < bestValue) best = entry;
  }
  return best;
}

function missingState(group: EvaluationRun[], now: number): VariantState {
  const newest = group[group.length - 1];
  if (!newest) return "not_run";
  if (!TERMINAL_RUN_STATUSES.has(newest.status)) return "waiting";
  if (newest.status === "cancelled" || !newest.finished_at) return "not_run";
  // The server starts the next variant as soon as one ends; past the grace period the chain stopped.
  return now - Date.parse(newest.finished_at) < NEXT_VARIANT_GRACE_MS
    ? "waiting"
    : "not_run";
}

/** The comparison a run belongs to, from the evaluation's runs; null when the run is not in one. */
export function buildComparison(
  runs: readonly EvaluationRun[],
  comparisonId: string,
  now: number = Date.now(),
): Comparison | null {
  const group = runs
    .filter((run) => run.config.comparison?.id === comparisonId)
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
  const plan = group[group.length - 1]?.config.comparison?.variants;
  if (!plan) return null;
  const byIndex = new Map<number, EvaluationRun>();
  for (const run of group) {
    const index = run.config.comparison?.index;
    if (typeof index === "number") byIndex.set(index, run);
  }
  const missing = missingState(group, now);
  const entries = plan.map((overrides, index) =>
    entryOf(index, overrides, byIndex.get(index) ?? null, missing),
  );
  const ranked = entries
    .filter(
      (entry) => RANKED_STATUSES.has(entry.state) && entry.passRate !== null,
    )
    .sort(compareEntries);
  const top = ranked[0];
  ranked.forEach((entry, position) => {
    entry.rank = position + 1;
    entry.matchesTop = position > 0 && entry.passRate === top?.passRate;
    entry.tiedWithTop = Boolean(
      position > 0 &&
        !entry.matchesTop &&
        top?.interval &&
        entry.interval &&
        entry.interval[1] >= top.interval[0],
    );
  });
  const costs = entries.map((entry) => entry.run?.summary?.cost_usd);
  const knownCosts = costs.filter((cost) => cost?.total != null);
  return {
    id: comparisonId,
    entries,
    ranked,
    mostAccurate: top ?? null,
    cheapest: lowest(ranked, (entry) => entry.cost),
    fastest: lowest(ranked, (entry) => entry.p50),
    totalCost: knownCosts.length
      ? knownCosts.reduce((sum, cost) => sum + (cost?.total ?? 0), 0)
      : null,
    finished: entries.filter(
      (entry) =>
        entry.run !== null && TERMINAL_RUN_STATUSES.has(entry.run.status),
    ).length,
  };
}
