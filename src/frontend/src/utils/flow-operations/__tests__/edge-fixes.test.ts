import editorCases from "../../../../../lfx-native/fixtures/editor_cases.json";
import type { FlowOperation } from "../apply";
import { edgeFixes, fixesForEdges } from "../edge-fixes";

type JsonObject = Record<string, unknown>;

const handles = (output: string, field: string) => ({
  sourceHandle: { name: output },
  targetHandle: { fieldName: field },
});

const edge = (id: string, output: string, field: string) => ({
  id,
  source: "a",
  target: "b",
  sourceHandle: `{œnameœ:œ${output}œ}`,
  targetHandle: `{œfieldNameœ:œ${field}œ}`,
  data: handles(output, field),
});

describe("edgeFixes", () => {
  it("is empty when the preview changed no edge", () => {
    const edges = [edge("e1", "out", "text")];

    expect(edgeFixes(edges, [{ ...edges[0], selected: false }])).toEqual([]);
  });

  it("deletes the edges the preview dropped", () => {
    expect(
      edgeFixes(
        [edge("e1", "out", "text"), edge("e2", "out", "other")],
        [edge("e1", "out", "text")],
      ),
    ).toEqual([{ type: "delete_edges", ids: ["e2"] }]);
  });

  it("deletes and adds again an edge whose handles the preview rewrote", () => {
    const read = edge("e1", "out", "text");
    const shown = edge("e1", "out", "input_value");

    expect(edgeFixes([read], [shown])).toEqual([
      { type: "delete_edges", ids: ["e1"] },
      { type: "add_edges", edges: [shown] },
    ]);
  });

  it("gives an edge read without data a data object with its handles", () => {
    const { data: _data, ...read } = edge("e1", "out", "text");
    const shown = edge("e1", "out", "text");

    expect(edgeFixes([read], [shown])).toEqual([
      { type: "delete_edges", ids: ["e1"] },
      { type: "add_edges", edges: [{ ...read, data: handles("out", "text") }] },
    ]);
  });

  it("keeps the other keys of the edge as read", () => {
    const read = { ...edge("e1", "out", "text"), animated: true };
    const shown = edge("e1", "out", "input_value");

    expect(edgeFixes([read], [shown])).toEqual([
      { type: "delete_edges", ids: ["e1"] },
      { type: "add_edges", edges: [{ ...shown, animated: true }] },
    ]);
  });

  it("removes a handle the shown edge lacks", () => {
    const read = edge("e1", "out", "text");
    const { targetHandle: _targetHandle, ...shown } = edge("e1", "out", "text");

    expect(edgeFixes([read], [shown])).toStrictEqual([
      { type: "delete_edges", ids: ["e1"] },
      { type: "add_edges", edges: [shown] },
    ]);
  });

  it.each(editorCases.edge_fixes)("$name", (testCase) => {
    expect(
      edgeFixes(testCase.read as JsonObject[], testCase.shown as JsonObject[]),
    ).toEqual(testCase.fixes);
  });
});

describe("fixesForEdges", () => {
  it("keeps only the fixes for the given edges, dropping operations left empty", () => {
    const fixes = [
      { type: "delete_edges", ids: ["a", "b", "c"] },
      { type: "add_edges", edges: [edge("c", "out", "text")] },
    ];

    expect(fixesForEdges(fixes, new Set(["b"]))).toEqual([
      { type: "delete_edges", ids: ["b"] },
    ]);
    expect(fixesForEdges(fixes, new Set(["c"]))).toEqual([
      { type: "delete_edges", ids: ["c"] },
      { type: "add_edges", edges: [edge("c", "out", "text")] },
    ]);
  });

  it.each(editorCases.fixes_for_edges)("$name", (testCase) => {
    expect(
      fixesForEdges(
        testCase.fixes as FlowOperation[],
        new Set(testCase.edge_ids),
      ),
    ).toEqual(testCase.expected);
  });
});
