import { createHash } from "crypto";
import {
  canonicalGraphJson,
  canonicalHandle,
  canonicalJson,
  valuesEqual,
} from "../canonical";

// Expected strings and hashes are what the engine's
// `lfx.services.flow_operations.canonical` prints for the same values.
describe("canonicalJson", () => {
  it("sorts keys and prints numbers as RFC 8785 does", () => {
    expect(
      canonicalJson({
        b: 1,
        a: [1.5, 1e21, 1e-7, 0.1, -0, 2 ** 53 + 1, 123456789.125],
        é: 'é\n"',
        Z: true,
        aa: null,
      }),
    ).toBe(
      '{"Z":true,"a":[1.5,1e+21,1e-7,0.1,0,9007199254740992,123456789.125],"aa":null,"b":1,"é":"é\\n\\""}',
    );
  });

  it("orders keys by UTF-16 code units", () => {
    expect(canonicalJson({ ﬁ: 3, "\u{1F600}": 2, "€": 1 })).toBe(
      '{"€":1,"😀":2,"ﬁ":3}',
    );
  });

  it("refuses values JSON cannot hold", () => {
    expect(() => canonicalJson({ a: Number.NaN })).toThrow();
    expect(() => canonicalJson({ a: undefined })).toThrow();
  });
});

describe("valuesEqual", () => {
  it("ignores key order and compares by value", () => {
    expect(
      valuesEqual({ a: 1, b: [1, { c: 2 }] }, { b: [1, { c: 2 }], a: 1 }),
    ).toBe(true);
    expect(valuesEqual({ a: 1 }, { a: 2 })).toBe(false);
    expect(valuesEqual("1", 1)).toBe(false);
    expect(valuesEqual(null, null)).toBe(true);
    expect(valuesEqual(true, 1)).toBe(false);
  });
});

describe("canonicalHandle", () => {
  it("spells one handle one way", () => {
    expect(canonicalHandle("{œnameœ: œoutœ, œidœ:œaœ}")).toBe(
      "{œidœ:œaœ,œnameœ:œoutœ}",
    );
    expect(canonicalHandle("not json")).toBe("not json");
    expect(canonicalHandle(3)).toBe(3);
  });
});

describe("canonicalGraphJson", () => {
  it("drops view state, orders nodes and edges by id, and hashes as the engine does", () => {
    const graph = {
      viewport: { x: 1 },
      nodes: [
        {
          id: "b",
          selected: true,
          data: {
            node: {
              lf_version: "1",
              template: {
                _frontend_node_flow_id: "x",
                f: { value: 1, display_name: "F" },
              },
            },
          },
        },
        { id: "a", data: {} },
      ],
      edges: [
        {
          id: "e",
          source: "a",
          target: "b",
          animated: true,
          sourceHandle: "{œnameœ: œoutœ, œidœ:œaœ}",
        },
      ],
    };

    const json = canonicalGraphJson(graph);

    expect(json).toBe(
      '{"edges":[{"id":"e","source":"a","sourceHandle":"{œidœ:œaœ,œnameœ:œoutœ}","target":"b"}],"nodes":[{"data":{},"id":"a"},{"data":{"node":{"template":{"f":{"value":1}}}},"id":"b"}]}',
    );
    const hash = createHash("sha256").update(json, "utf8").digest("hex");
    const engineHash =
      "e2c0ea8953549d81cdcb3fa5386ef1bb2cfc9524931e984001db8dc93c74f274"; // pragma: allowlist secret
    expect(hash).toBe(engineHash);
    expect(graph.nodes[0].selected).toBe(true);
  });
});
