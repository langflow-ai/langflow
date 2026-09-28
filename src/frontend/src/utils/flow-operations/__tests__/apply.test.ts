import { cloneDeep } from "lodash";
import golden from "../../../../../lfx/tests/unit/services/flow_operations/fixtures/apply_cases.json";
import {
  applyFlowOperations,
  type FlowOperation,
  FlowOperationError,
} from "../apply";

type GoldenCase = {
  name: string;
  base: unknown;
  operations: FlowOperation[];
  expected?: unknown;
  forward_operations?: FlowOperation[];
  error?: string;
  code?: string;
};

// The same cases the server's engine runs: any disagreement between the two
// appliers fails one side or the other.
describe("applyFlowOperations matches the server engine", () => {
  it.each((golden as { cases: GoldenCase[] }).cases.map((c) => [c.name, c]))(
    "%s",
    (_name, testCase) => {
      const base = cloneDeep(testCase.base);

      if (testCase.error) {
        let caught: unknown;
        try {
          applyFlowOperations(base, cloneDeep(testCase.operations));
        } catch (error) {
          caught = error;
        }
        expect(caught).toBeInstanceOf(FlowOperationError);
        expect((caught as FlowOperationError).name).toBe(testCase.error);
        expect((caught as FlowOperationError).code).toBe(testCase.code);
      } else {
        const result = applyFlowOperations(
          base,
          cloneDeep(testCase.operations),
        );
        expect(result.flowData).toEqual(testCase.expected);
        expect(result.forwardOperations).toEqual(testCase.forward_operations);
      }
      expect(base).toEqual(testCase.base);
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
