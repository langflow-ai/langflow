import { edgeFixes, fixesForEdges } from "../edge-fixes";

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

  it("rewrites the handles the preview rewrote, in both forms", () => {
    const read = edge("e1", "out", "text");
    const shown = edge("e1", "out", "input_value");

    expect(edgeFixes([read], [shown])).toEqual([
      {
        type: "update_edges",
        updates: [
          {
            id: "e1",
            op: "set_field",
            path: ["targetHandle"],
            value: shown.targetHandle,
          },
          {
            id: "e1",
            op: "set_field",
            path: ["data", "targetHandle"],
            value: { fieldName: "input_value" },
          },
        ],
      },
    ]);
  });

  it("writes the data of an edge read without it whole", () => {
    const { data: _data, ...read } = edge("e1", "out", "text");
    const shown = edge("e1", "out", "text");

    expect(edgeFixes([read], [shown])).toEqual([
      {
        type: "update_edges",
        updates: [
          {
            id: "e1",
            op: "set_field",
            path: ["data"],
            value: handles("out", "text"),
          },
        ],
      },
    ]);
  });
});

describe("fixesForEdges", () => {
  it("keeps only the fixes for the given edges, dropping operations left empty", () => {
    const fixes = [
      { type: "delete_edges", ids: ["a", "b"] },
      {
        type: "update_edges",
        updates: [{ id: "c", op: "set_field", path: ["data"], value: {} }],
      },
    ];

    expect(fixesForEdges(fixes, new Set(["b"]))).toEqual([
      { type: "delete_edges", ids: ["b"] },
    ]);
  });
});
