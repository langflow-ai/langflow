// Same defaults and bounds as the server (scorers/llm_judge.py).
export const DEFAULT_JUDGE_MAX_OUTPUT_TOKENS = 600;
export const DEFAULT_JUDGE_MAX_RUN_OUTPUT_TOKENS = 8192;
export const JUDGE_MAX_OUTPUT_TOKENS_CEILING = 32768;
export const JUDGE_MAX_RUN_OUTPUT_TOKENS_CEILING = 10_000_000;

function parseWholeNumber(raw: string, ceiling: number): number | null {
  if (!/^\d+$/.test(raw.trim())) return null;
  const value = Number(raw.trim());
  return value >= 1 && value <= ceiling ? value : null;
}

/** The per-row budget as a whole number in range, or null when it cannot be submitted. */
export function parseJudgeMaxTokens(raw: string): number | null {
  return parseWholeNumber(raw, JUDGE_MAX_OUTPUT_TOKENS_CEILING);
}

/** The per-run budget; it must also cover at least one row. */
export function parseJudgeRunMaxTokens(
  raw: string,
  rowBudget: number | null,
): number | null {
  const value = parseWholeNumber(raw, JUDGE_MAX_RUN_OUTPUT_TOKENS_CEILING);
  if (value === null || (rowBudget !== null && value < rowBudget)) return null;
  return value;
}

export function isReasoningModel(metadata: unknown): boolean {
  return (
    typeof metadata === "object" &&
    metadata !== null &&
    (metadata as { reasoning?: unknown }).reasoning === true
  );
}
