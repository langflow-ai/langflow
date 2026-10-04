import { createHash } from "crypto";
import { readFileSync } from "fs";
import { cloneDeep } from "lodash";
import { join } from "path";
import golden from "../../../../../lfx/tests/unit/services/flow_operations/fixtures/apply_cases.json";
import mergeCases from "../../../../../lfx/tests/unit/services/flow_operations/fixtures/merge_cases.json";
import propertyCases from "../../../../../lfx/tests/unit/services/flow_operations/fixtures/property_cases.json";
import {
  applyFlowOperations,
  type FlowGraph,
  type FlowOperation,
  FlowOperationError,
} from "../apply";
import { canonicalGraphJson } from "../canonical";

type GoldenCase = {
  name: string;
  base: unknown;
  operations: FlowOperation[];
  expected?: unknown;
  forward_operations?: FlowOperation[];
  error?: string;
  code?: string;
};

type MergeCase = {
  name: string;
  transactions: Record<string, FlowOperation[]>;
  order: string[];
  outcomes: Record<string, "applied" | { error: string; code: string }>;
  expected: unknown;
};

type PropertySequence = {
  name: string;
  transactions: FlowOperation[][];
  graph_hash: string;
};

const ENGINE_DIR = join(
  __dirname,
  "../../../../../lfx/src/lfx/services/flow_operations",
);

function caught(run: () => unknown): FlowOperationError {
  try {
    run();
  } catch (error) {
    expect(error).toBeInstanceOf(FlowOperationError);
    return error as FlowOperationError;
  }
  throw new Error("expected the operations to be refused");
}

function graphHash(graph: FlowGraph): string {
  return createHash("sha256")
    .update(canonicalGraphJson(graph), "utf8")
    .digest("hex");
}

describe("node_schema.json", () => {
  it("is a byte-identical copy of the engine's", () => {
    const engine = readFileSync(join(ENGINE_DIR, "node_schema.json"));
    const editor = readFileSync(join(__dirname, "../node_schema.json"));

    expect(editor.equals(engine)).toBe(true);
  });
});

// The same cases the server's engine runs: any disagreement between the two
// appliers fails one side or the other.
describe("applyFlowOperations matches the server engine", () => {
  it.each((golden as { cases: GoldenCase[] }).cases.map((c) => [c.name, c]))(
    "%s",
    (_name, testCase) => {
      const base = cloneDeep(testCase.base);

      if (testCase.error) {
        const error = caught(() =>
          applyFlowOperations(base, cloneDeep(testCase.operations)),
        );
        expect(error.name).toBe(testCase.error);
        expect(error.code).toBe(testCase.code);
      } else {
        const result = applyFlowOperations(
          base,
          cloneDeep(testCase.operations),
        );
        expect(result.flowData).toEqual(testCase.expected);
        // Cases whose normalized operations equal what they submit leave
        // forward_operations out.
        expect(result.forwardOperations).toEqual(
          testCase.forward_operations ?? testCase.operations,
        );
      }
      expect(base).toEqual(testCase.base);
    },
  );
});

describe("transactions applied in order merge as on the server", () => {
  const document = mergeCases as unknown as {
    base: FlowGraph;
    cases: MergeCase[];
  };

  it.each(document.cases.map((c) => [c.name, c]))("%s", (_name, testCase) => {
    let graph = cloneDeep(document.base);
    const outcomes: MergeCase["outcomes"] = {};
    for (const name of testCase.order) {
      const before = cloneDeep(graph);
      try {
        graph = applyFlowOperations(
          graph,
          cloneDeep(testCase.transactions[name]),
        ).flowData;
        outcomes[name] = "applied";
      } catch (error) {
        expect(error).toBeInstanceOf(FlowOperationError);
        const { name: errorName, code } = error as FlowOperationError;
        outcomes[name] = { error: errorName, code };
        expect(graph).toEqual(before);
      }
    }

    expect(outcomes).toEqual(testCase.outcomes);
    expect(graph).toEqual(testCase.expected);
  });
});

describe("random transactions replay to the engine's hashes", () => {
  const document = propertyCases as unknown as {
    base: FlowGraph;
    sequences: PropertySequence[];
  };

  it.each(document.sequences.map((s) => [s.name, s]))(
    "%s",
    (_name, sequence) => {
      let graph = cloneDeep(document.base);
      for (const transaction of sequence.transactions) {
        graph = applyFlowOperations(graph, cloneDeep(transaction)).flowData;
      }

      expect(graphHash(graph)).toBe(sequence.graph_hash);
    },
  );
});

describe("applyFlowOperations copies on write", () => {
  const node = (id: string) => ({
    id,
    data: { node: { template: { text: { value: id } } } },
  });

  it("shares every node an operation did not touch", () => {
    const base = { nodes: [node("a"), node("b")], edges: [] };

    const { flowData } = applyFlowOperations(base, [
      {
        type: "update_nodes",
        updates: [
          {
            id: "a",
            op: "set_field",
            path: ["data", "node", "template", "text", "value"],
            value: "changed",
          },
        ],
      },
    ]);

    expect(flowData.nodes[1]).toBe(base.nodes[1]);
    expect(flowData.nodes[0]).not.toBe(base.nodes[0]);
    expect(base.nodes[0].data.node.template.text.value).toBe("a");
  });
});

describe("applyFlowOperations in redacted mode", () => {
  const typeChange = {
    type: "update_nodes",
    updates: [
      {
        id: "a",
        op: "set_field",
        path: ["data", "node", "template", "api_key", "value"],
        value: null,
      },
    ],
  };
  const base = () => ({
    nodes: [
      { id: "a", data: { node: { template: { api_key: { value: "" } } } } },
    ],
    edges: [],
  });

  it("rejects an undeclared type change by default", () => {
    expect(caught(() => applyFlowOperations(base(), [typeChange])).code).toBe(
      "FIELD_TYPE_CHANGE_UNDECLARED",
    );
  });

  it("allows it when replaying operations read with secrets removed", () => {
    const { flowData } = applyFlowOperations(base(), [typeChange], {
      redacted: true,
    });

    expect(flowData.nodes[0]).toEqual({
      id: "a",
      data: { node: { template: { api_key: { value: null } } } },
    });
  });
});

describe("applyFlowOperations while restoring", () => {
  const graph = () => ({
    nodes: [
      { id: "s", data: { node: { template: {}, outputs: [{ name: "out" }] } } },
      { id: "d", data: { node: { template: { one: { type: "str" } } } } },
    ],
    edges: [],
  });
  const stale = {
    type: "add_edges",
    edges: [
      {
        id: "e",
        source: "s",
        target: "d",
        data: {
          sourceHandle: { name: "out" },
          targetHandle: { fieldName: "gone" },
        },
      },
    ],
  };

  it("puts back an edge the rules would refuse", () => {
    expect(caught(() => applyFlowOperations(graph(), [stale])).code).toBe(
      "EDGE_HANDLE_NOT_FOUND",
    );
    expect(
      applyFlowOperations(graph(), [stale], { restoring: true }).flowData.edges,
    ).toHaveLength(1);
  });
});
