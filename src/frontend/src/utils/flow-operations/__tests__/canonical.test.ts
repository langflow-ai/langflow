import { createHash } from "crypto";
import {
  canonicalGraphJson,
  canonicalJson,
  graphsEqual,
  orderedRows,
  parseHandle,
  valuesEqual,
} from "../canonical";
import { FlowOperationError } from "../errors";

function caught(run: () => unknown): FlowOperationError {
  try {
    run();
  } catch (error) {
    expect(error).toBeInstanceOf(FlowOperationError);
    return error as FlowOperationError;
  }
  throw new Error("expected an engine error");
}

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

  // The engine's canonical tests use the same digits: the smallest integer
  // past the largest double, its negation, and 10**309. JSON.parse reads each
  // as Infinity, which is not a finite JSON number.
  it.each([
    "179769313486231580793728971405303415079934132710037826936173778980444968292764750946649017977587207096330286416692887910946555547851940402630657488671505820681908902000708383676273854845817711531764475730270069855571366959622842914819860834936475292719074168444365510704342711559699508093042880177904174497792",
    "-179769313486231580793728971405303415079934132710037826936173778980444968292764750946649017977587207096330286416692887910946555547851940402630657488671505820681908902000708383676273854845817711531764475730270069855571366959622842914819860834936475292719074168444365510704342711559699508093042880177904174497792",
    `1${"0".repeat(309)}`,
  ])("refuses an integer too large for a double", (digits) => {
    const value = JSON.parse(digits);
    expect(caught(() => canonicalJson({ x: value })).name).toBe(
      "FlowDataValidationError",
    );
    expect(caught(() => valuesEqual(value, 1)).name).toBe(
      "FlowDataValidationError",
    );
  });

  // JSON texts the engine's canonical tests parse too. JSON.parse keeps an
  // unpaired surrogate escape as one, and joins an escaped pair.
  it.each([
    String.raw`"\ud800"`,
    String.raw`"a\udc00"`,
    String.raw`"\ude00x"`,
    String.raw`"x\ud83d"`,
    String.raw`"\ud800\ud800\udc00"`,
    String.raw`{"\ud800": 1}`,
    String.raw`[{"k": "\udfff"}]`,
  ])("refuses an unpaired surrogate in %s", (text) => {
    expect(caught(() => canonicalJson(JSON.parse(text))).name).toBe(
      "FlowDataValidationError",
    );
  });

  it("prints a surrogate pair as its character", () => {
    expect(
      canonicalJson(JSON.parse(String.raw`{"\ud83d\ude00": "\ud83d\ude00"}`)),
    ).toBe('{"\u{1F600}":"\u{1F600}"}');
  });

  it("prints an integer just below the double overflow as the largest double", () => {
    expect(
      canonicalJson(
        JSON.parse(
          "179769313486231580793728971405303415079934132710037826936173778980444968292764750946649017977587207096330286416692887910946555547851940402630657488671505820681908902000708383676273854845817711531764475730270069855571366959622842914819860834936475292719074168444365510704342711559699508093042880177904174497791",
        ),
      ),
    ).toBe("1.7976931348623157e+308");
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

describe("parseHandle", () => {
  it("reads the object a handle string encodes", () => {
    expect(parseHandle("{œnameœ: œoutœ, œidœ:œaœ}")).toEqual({
      id: "a",
      name: "out",
    });
    expect(parseHandle("not json")).toBeNull();
    expect(parseHandle("[1]")).toBeNull();
    expect(parseHandle(3)).toBeNull();
  });

  // The engine's canonical tests read the same strings.
  it.each([
    "{œnameœ:œoutœ,œxœ:NaN}",
    "{œnameœ:œoutœ,œxœ:Infinity}",
    "{œnameœ:œoutœ,œxœ:-Infinity}",
  ])("does not parse a non-finite token in %s", (handle) => {
    expect(parseHandle(handle)).toBeNull();
  });
});

describe("orderedRows", () => {
  it("orders rows by position, then id", () => {
    const rows = [
      { _id: "r2", _pos: 1 },
      { _id: "r1", _pos: 1 },
      { _id: "r0", _pos: 0.5 },
    ];

    expect(orderedRows(rows).map((row) => row._id)).toEqual(["r0", "r1", "r2"]);
    expect(rows[0]._id).toBe("r2");
  });

  it("keeps a legacy table as stored", () => {
    const rows = [{ k: "b" }, { _id: "r1", _pos: 1 }];

    expect(orderedRows(rows)).toEqual(rows);
  });
});

describe("graphsEqual", () => {
  const graph = (rows: unknown[], edgeHandle: unknown) => ({
    nodes: [
      { id: "a", data: { node: { template: {} } } },
      {
        id: "b",
        data: { node: { template: { rows: { type: "table", value: rows } } } },
      },
    ],
    edges: [{ id: "e", source: "a", target: "b", sourceHandle: edgeHandle }],
  });
  const r1 = { _id: "r1", _pos: 1, k: "x" };
  const r2 = { _id: "r2", _pos: 2, k: "y" };

  it("ignores the array order of nodes, edges and table rows", () => {
    const left = graph([r1, r2], "{œnameœ:œoutœ,œidœ:œaœ}");
    const right = graph([r2, r1], "{œidœ: œaœ, œnameœ: œoutœ}");
    right.nodes.reverse();

    expect(graphsEqual(left, right)).toBe(true);
  });

  it("tells a moved row apart", () => {
    expect(
      graphsEqual(graph([r1, r2], null), graph([{ ...r1, _pos: 3 }, r2], null)),
    ).toBe(false);
  });
});

describe("canonicalGraphJson", () => {
  it("drops view state, parses handles, orders nodes, edges and rows, and hashes as the engine does", () => {
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
                rows: {
                  type: "table",
                  value: [
                    { _id: "r2", _pos: 1, k: "y" },
                    { _id: "r1", _pos: 1, k: "x" },
                    { _id: "r0", _pos: 0.5, k: "w" },
                  ],
                },
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
      '{"edges":[{"id":"e","source":"a","sourceHandle":{"id":"a","name":"out"},"target":"b"}],"nodes":[{"data":{},"id":"a"},{"data":{"node":{"template":{"f":{"value":1},"rows":{"type":"table","value":[{"_id":"r0","_pos":0.5,"k":"w"},{"_id":"r1","_pos":1,"k":"x"},{"_id":"r2","_pos":1,"k":"y"}]}}}},"id":"b"}]}',
    );
    const hash = createHash("sha256").update(json, "utf8").digest("hex");
    const engineHash =
      "e683ad9b0684adab86da961ac7b37d46bca3ddd1b09ae593fa56accaeb08184f"; // pragma: allowlist secret
    expect(hash).toBe(engineHash);
    expect(graph.nodes[0].selected).toBe(true);
  });
});
