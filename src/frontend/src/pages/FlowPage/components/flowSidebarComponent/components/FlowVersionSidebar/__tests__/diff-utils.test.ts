import {
  buildSummaryChips,
  describeDiffSide,
  formatDiffValue,
  MAX_RENDERED_VALUE_CHARS,
  parseUnifiedDiffLines,
} from "../diff-utils";

const emptySummary = {
  nodes_added: 0,
  nodes_removed: 0,
  nodes_modified: 0,
  nodes_unchanged: 0,
  edges_added: 0,
  edges_removed: 0,
  edges_unchanged: 0,
  fields_changed: 0,
  code_fields_changed: 0,
  secrets_changed: 0,
};

describe("formatDiffValue", () => {
  it("renders an absent value as an empty string", () => {
    expect(formatDiffValue(undefined)).toBe("");
  });

  it("distinguishes an explicit null from an absent value", () => {
    expect(formatDiffValue(null)).toBe("null");
  });

  it("renders scalars without quoting", () => {
    expect(formatDiffValue("hello")).toBe("hello");
    expect(formatDiffValue(0.7)).toBe("0.7");
    expect(formatDiffValue(false)).toBe("false");
  });

  it("serializes structured values", () => {
    expect(formatDiffValue({ a: 1 })).toBe('{\n  "a": 1\n}');
    expect(formatDiffValue([1, 2])).toBe("[\n  1,\n  2\n]");
  });

  it("clamps a long value so one prompt cannot blow out the dialog", () => {
    const long = "a".repeat(MAX_RENDERED_VALUE_CHARS + 50);

    const rendered = formatDiffValue(long);

    expect(rendered).toHaveLength(MAX_RENDERED_VALUE_CHARS + 1);
    expect(rendered.endsWith("…")).toBe(true);
  });

  it("does not throw on a circular structure", () => {
    const circular: Record<string, unknown> = {};
    circular.self = circular;

    expect(formatDiffValue(circular)).toBe("[unserializable]");
  });
});

describe("parseUnifiedDiffLines", () => {
  it("returns nothing for an absent diff", () => {
    expect(parseUnifiedDiffLines(null)).toEqual([]);
    expect(parseUnifiedDiffLines(undefined)).toEqual([]);
  });

  it("classifies added, removed, meta and context lines", () => {
    const diff = [
      "--- ",
      "+++ ",
      "@@ -1,2 +1,2 @@",
      " ctx",
      "-old",
      "+new",
    ].join("\n");

    expect(parseUnifiedDiffLines(diff).map((line) => line.kind)).toEqual([
      "meta",
      "meta",
      "meta",
      "ctx",
      "del",
      "add",
    ]);
  });

  it("does not mistake the file headers for additions or removals", () => {
    const lines = parseUnifiedDiffLines("+++ \n--- ");

    expect(lines.every((line) => line.kind === "meta")).toBe(true);
  });
});

describe("buildSummaryChips", () => {
  it("returns nothing without a summary", () => {
    expect(buildSummaryChips(undefined)).toEqual([]);
  });

  it("omits zero counts", () => {
    expect(buildSummaryChips(emptySummary)).toEqual([]);
  });

  it("keeps non-zero counts in a stable reading order", () => {
    const chips = buildSummaryChips({
      ...emptySummary,
      nodes_added: 2,
      edges_removed: 1,
      secrets_changed: 3,
    });

    expect(chips.map((chip) => chip.key)).toEqual([
      "nodes_added",
      "edges_removed",
      "secrets_changed",
    ]);
    expect(chips.map((chip) => chip.tone)).toEqual([
      "added",
      "removed",
      "secret",
    ]);
  });
});

describe("describeDiffSide", () => {
  it("labels the draft side with the supplied label", () => {
    expect(describeDiffSide({ kind: "draft" }, "Current")).toBe("Current");
  });

  it("labels a version side with its tag", () => {
    expect(
      describeDiffSide({ kind: "version", version_tag: "v3" }, "Current"),
    ).toBe("v3");
  });

  it("returns an empty label when the side is not loaded yet", () => {
    expect(describeDiffSide(undefined, "Current")).toBe("");
  });
});
