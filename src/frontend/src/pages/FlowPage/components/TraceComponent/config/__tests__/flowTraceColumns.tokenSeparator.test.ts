// Tests for the token column returned by createFlowTracesColumns.
// Calls the actual production valueGetter to verify locale-formatted output.

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/i18n", () => ({
  __esModule: true,
  default: { t: (k: string) => k },
}));

jest.mock("@/utils/dateTime", () => ({
  formatSmartTimestamp: () => "",
}));

jest.mock("../../traceViewHelpers", () => ({
  formatTotalLatency: () => "",
  getStatusIconProps: () => ({
    colorClass: "",
    iconName: "Circle",
    shouldSpin: false,
  }),
}));

import type { ColDef } from "ag-grid-community";
import { createFlowTracesColumns } from "../flowTraceColumns";

function getTokenColumn(): ColDef {
  const cols = createFlowTracesColumns({ flowId: "f1", flowName: "Flow" });
  const col = cols.find((c) => c.field === "totalTokens");
  if (!col) throw new Error("totalTokens column not found");
  return col;
}

function callValueGetter(col: ColDef, data: Record<string, unknown>): string {
  if (typeof col.valueGetter !== "function") {
    throw new Error("valueGetter is not a function");
  }
  return col.valueGetter({ data } as never) as string;
}

describe("flowTraceColumns — totalTokens column valueGetter", () => {
  it("returns empty string when both totalTokens and total_tokens are absent", () => {
    const col = getTokenColumn();
    expect(callValueGetter(col, {})).toBe("");
    expect(
      callValueGetter(col, { totalTokens: undefined, total_tokens: undefined }),
    ).toBe("");
    expect(
      callValueGetter(col, { totalTokens: null, total_tokens: null }),
    ).toBe("");
  });

  it("formats small numbers with toLocaleString (camelCase field)", () => {
    const col = getTokenColumn();
    expect(callValueGetter(col, { totalTokens: 42 })).toBe(
      (42).toLocaleString(),
    );
  });

  it("formats large numbers with locale thousands separator (camelCase field)", () => {
    const col = getTokenColumn();
    const result = callValueGetter(col, { totalTokens: 12345 });
    expect(result).toBe((12345).toLocaleString());
    expect(result).not.toBe("12345");
  });

  it("falls back to snake_case total_tokens when camelCase is empty", () => {
    const col = getTokenColumn();
    const result = callValueGetter(col, { totalTokens: "", total_tokens: 999 });
    expect(result).toBe((999).toLocaleString());
  });

  it("prefers camelCase totalTokens over snake_case total_tokens", () => {
    const col = getTokenColumn();
    expect(callValueGetter(col, { totalTokens: 100, total_tokens: 200 })).toBe(
      (100).toLocaleString(),
    );
  });

  it("formats a million tokens with locale separator", () => {
    const col = getTokenColumn();
    const result = callValueGetter(col, { totalTokens: 1_000_000 });
    expect(result).toBe((1_000_000).toLocaleString());
    expect(result.length).toBeGreaterThan(7);
  });
});
