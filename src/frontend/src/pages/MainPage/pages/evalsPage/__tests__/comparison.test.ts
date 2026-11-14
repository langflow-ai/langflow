import { buildComparison, wilsonInterval } from "../utils/comparison";
import { PLAN, variantRun } from "./comparisonFixtures";

const NOW = Date.parse("2026-10-30T11:00:10Z");

describe("wilsonInterval", () => {
  it("should bracket the rate and stay within 0 and 1", () => {
    const [low, high] = wilsonInterval(8, 10) ?? [0, 0];
    expect(low).toBeGreaterThan(0.4);
    expect(low).toBeLessThan(0.8);
    expect(high).toBeGreaterThan(0.8);
    expect(high).toBeLessThan(1);
    expect(wilsonInterval(10, 10)?.[1]).toBe(1);
    expect(wilsonInterval(0, 10)?.[0]).toBe(0);
  });

  it("should have no interval without decided rows", () => {
    expect(wilsonInterval(0, 0)).toBeNull();
  });
});

describe("buildComparison", () => {
  it("should rank by pass rate, then cost, then speed", () => {
    const runs = [
      variantRun({ index: 0, passed: 90, decided: 100, cost: 0.05, p50: 900 }),
      variantRun({ index: 1, passed: 90, decided: 100, cost: 0.01, p50: 2000 }),
      variantRun({ index: 2, passed: 60, decided: 100, cost: 0.001, p50: 200 }),
    ];

    const comparison = buildComparison(runs, "cmp-1", NOW);

    expect(comparison?.ranked.map((entry) => entry.index)).toEqual([1, 0, 2]);
    expect(comparison?.mostAccurate?.index).toBe(1);
    expect(comparison?.cheapest?.index).toBe(2);
    expect(comparison?.fastest?.index).toBe(2);
    expect(comparison?.totalCost).toBeCloseTo(0.061);
    expect(comparison?.finished).toBe(3);
  });

  it("should mark a version within the top one's margin of error, not a clearly worse one", () => {
    const runs = [
      variantRun({ index: 0, passed: 9, decided: 10 }),
      variantRun({ index: 1, passed: 8, decided: 10 }),
      variantRun({ index: 2, passed: 10, decided: 100 }),
    ];

    const ranked = buildComparison(runs, "cmp-1", NOW)?.ranked ?? [];

    expect(ranked.map((entry) => [entry.index, entry.tiedWithTop])).toEqual([
      [0, false],
      [1, true],
      [2, false],
    ]);
  });

  it("should call an equal pass rate a tie, not a margin-of-error match", () => {
    const runs = [
      variantRun({ index: 0, passed: 10, decided: 10, cost: 0.03 }),
      variantRun({ index: 1, passed: 10, decided: 10, cost: 0.01 }),
      variantRun({ index: 2, passed: 9, decided: 10, cost: 0.02 }),
    ];

    const ranked = buildComparison(runs, "cmp-1", NOW)?.ranked ?? [];

    expect(
      ranked.map((entry) => [entry.index, entry.matchesTop, entry.tiedWithTop]),
    ).toEqual([
      [1, false, false],
      [0, true, false],
      [2, false, true],
    ]);
  });

  it("should leave running and missing versions unranked and say why", () => {
    const runs = [
      variantRun({ index: 0 }),
      variantRun({ index: 1, status: "running" }),
    ];

    const entries = buildComparison(runs, "cmp-1", NOW)?.entries ?? [];

    expect(entries.map((entry) => [entry.state, entry.rank])).toEqual([
      ["completed", 1],
      ["running", null],
      ["waiting", null],
    ]);
  });

  it("should call the rest not run once a version was cancelled or the next never started", () => {
    const cancelled = buildComparison(
      [variantRun({ index: 0, status: "cancelled" })],
      "cmp-1",
      NOW,
    );
    const stalled = buildComparison(
      [variantRun({ index: 0, finishedAt: "2026-10-30T09:00:00Z" })],
      "cmp-1",
      NOW,
    );
    const justEnded = buildComparison([variantRun({ index: 0 })], "cmp-1", NOW);

    expect(cancelled?.entries[1].state).toBe("not_run");
    expect(cancelled?.ranked).toEqual([]);
    expect(stalled?.entries[2].state).toBe("not_run");
    expect(justEnded?.entries[1].state).toBe("waiting");
  });

  it("should rank a version that stopped early but never call an unknown cost the cheapest", () => {
    const runs = [
      variantRun({ index: 0, cost: null }),
      variantRun({
        index: 1,
        status: "failed",
        passed: 1,
        decided: 3,
        cost: 0.5,
      }),
      variantRun({ index: 2, cost: 0.2, p50: null }),
    ];

    const comparison = buildComparison(runs, "cmp-1", NOW);

    expect(comparison?.ranked.map((entry) => entry.index)).toEqual([2, 0, 1]);
    expect(comparison?.cheapest?.index).toBe(2);
    expect(comparison?.fastest?.index).toBe(0);
    expect(comparison?.totalCost).toBeCloseTo(0.7);
  });

  it("should ignore runs of other comparisons and runs outside any", () => {
    const other = variantRun({ index: 0 });
    other.config.comparison = { id: "cmp-2", index: 0, variants: PLAN };
    const plain = variantRun({ index: 1 });
    delete plain.config.comparison;

    expect(buildComparison([other, plain], "cmp-1", NOW)).toBeNull();
    expect(buildComparison([other], "cmp-2", NOW)?.entries).toHaveLength(3);
  });
});
