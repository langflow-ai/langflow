// Unit tests for the totalPages computation logic extracted from FlowInsightsContent.
// The bug: when the API returns pages=0 (empty result set), totalPages became 0,
// the guard effect set pageIndex=0, and the paginator rendered "-19-0 of 0 items".
// Fix: Math.max(1, ...) ensures totalPages is never 0.

function computeTotalPages(
  apiPages: number | undefined,
  totalRuns: number,
  pageSize: number,
): number {
  return Math.max(1, apiPages ?? Math.ceil(totalRuns / pageSize));
}

describe("computeTotalPages — regression for pages=0 producing pageIndex=0", () => {
  it("returns 1 when api reports pages=0 (empty result set)", () => {
    expect(computeTotalPages(0, 0, 20)).toBe(1);
  });

  it("returns 1 when api reports pages=0 regardless of pageSize", () => {
    expect(computeTotalPages(0, 0, 12)).toBe(1);
    expect(computeTotalPages(0, 0, 50)).toBe(1);
  });

  it("returns 1 when api returns undefined and totalRuns is 0", () => {
    expect(computeTotalPages(undefined, 0, 20)).toBe(1);
  });

  it("returns api-provided pages when valid and non-zero", () => {
    expect(computeTotalPages(5, 100, 20)).toBe(5);
  });

  it("computes from totalRuns when api pages is undefined", () => {
    expect(computeTotalPages(undefined, 100, 20)).toBe(5);
  });

  it("rounds up when totalRuns is not divisible by pageSize", () => {
    expect(computeTotalPages(undefined, 45, 20)).toBe(3);
  });

  it("returns 1 for a single partial page", () => {
    expect(computeTotalPages(undefined, 5, 20)).toBe(1);
  });

  it("never returns less than 1 regardless of inputs", () => {
    for (const apiPages of [0, -1, undefined]) {
      for (const totalRuns of [0, 1, 10]) {
        expect(
          computeTotalPages(apiPages as number | undefined, totalRuns, 20),
        ).toBeGreaterThanOrEqual(1);
      }
    }
  });
});
