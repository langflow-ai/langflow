import { BuildStatus } from "@/constants/enums";
import type { AllNodeType, EdgeType } from "@/types/flow";
import type { FlowStoreType } from "@/types/zustand/flow";
import { getBranchSkip } from "../get-branch-skip";

type Output = { name: string; display_name: string };

const branchNode = (
  id: string,
  displayName: string,
  outputs: Output[],
): AllNodeType =>
  ({
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: { id, type: "Router", node: { display_name: displayName, outputs } },
  }) as unknown as AllNodeType;

const edge = (source: string, output: string, target: string): EdgeType =>
  ({
    id: `${source}-${output}-${target}`,
    source,
    target,
    data: { sourceHandle: { name: output }, targetHandle: {} },
  }) as unknown as EdgeType;

const skipped = (
  ids: string[],
  by: string,
): FlowStoreType["flowBuildStatus"] =>
  Object.fromEntries(
    ids.map((id) => [id, { status: BuildStatus.INACTIVE, skippedBy: by }]),
  );

const IF_ELSE_OUTPUTS = [
  { name: "true_result", display_name: "True" },
  { name: "false_result", display_name: "False" },
];

const SMART_ROUTER_OUTPUTS = [
  { name: "category_1_result", display_name: "Billing" },
  { name: "category_2_result", display_name: "Sales" },
  { name: "default_result", display_name: "Else" },
];

describe("getBranchSkip", () => {
  it("should_name_the_taken_if_else_output_when_the_clicked_branch_was_skipped", () => {
    const nodes = [branchNode("router", "If-Else", IF_ELSE_OUTPUTS)];
    const edges = [
      edge("router", "true_result", "out-true"),
      edge("router", "false_result", "out-false"),
    ];

    const skip = getBranchSkip(
      "out-false",
      skipped(["out-false"], "router"),
      nodes,
      edges,
    );

    expect(skip).toEqual({ component: "If-Else", outputs: ["True"] });
  });

  it.each(["Language Model", "Decision Model"])(
    "should_name_the_taken_smart_router_route_in_%s_mode",
    () => {
      const nodes = [branchNode("router", "Smart Router", SMART_ROUTER_OUTPUTS)];
      const edges = [
        edge("router", "category_1_result", "billing"),
        edge("router", "category_2_result", "sales"),
        edge("router", "default_result", "else"),
      ];

      const skip = getBranchSkip(
        "billing",
        skipped(["billing", "else"], "router"),
        nodes,
        edges,
      );

      expect(skip).toEqual({ component: "Smart Router", outputs: ["Sales"] });
    },
  );

  it("should_name_a_taken_output_even_when_nothing_is_connected_to_it", () => {
    const nodes = [branchNode("router", "If-Else", IF_ELSE_OUTPUTS)];
    const edges = [edge("router", "false_result", "out-false")];

    const skip = getBranchSkip(
      "out-false",
      skipped(["out-false"], "router"),
      nodes,
      edges,
    );

    expect(skip).toEqual({ component: "If-Else", outputs: ["True"] });
  });

  it("should_return_null_when_no_branch_skipped_the_node", () => {
    const nodes = [branchNode("router", "If-Else", IF_ELSE_OUTPUTS)];

    expect(
      getBranchSkip(
        "out-false",
        { "out-false": { status: BuildStatus.INACTIVE } },
        nodes,
        [],
      ),
    ).toBeNull();
    expect(getBranchSkip("out-false", {}, nodes, [])).toBeNull();
  });

  it("should_return_null_when_the_branch_node_is_gone", () => {
    expect(
      getBranchSkip("out-false", skipped(["out-false"], "router"), [], []),
    ).toBeNull();
  });
});
