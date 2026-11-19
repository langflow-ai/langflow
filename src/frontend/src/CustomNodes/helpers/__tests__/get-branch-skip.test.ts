import { BuildStatus } from "@/constants/enums";
import type { AllNodeType } from "@/types/flow";
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

const skipped = (
  id: string,
  by: string,
  takenOutputs: string[],
): FlowStoreType["flowBuildStatus"] => ({
  [id]: { status: BuildStatus.INACTIVE, skippedBy: by, takenOutputs },
});

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

    const skip = getBranchSkip(
      "out-false",
      skipped("out-false", "router", ["true_result"]),
      nodes,
    );

    expect(skip).toEqual({ component: "If-Else", outputs: ["True"] });
  });

  it("should_list_only_the_outputs_the_backend_reported_as_taken", () => {
    // Else is enabled but unconnected, and the router did not take it.
    const nodes = [branchNode("router", "Smart Router", SMART_ROUTER_OUTPUTS)];

    const skip = getBranchSkip(
      "billing",
      skipped("billing", "router", ["category_2_result"]),
      nodes,
    );

    expect(skip).toEqual({ component: "Smart Router", outputs: ["Sales"] });
  });

  it("should_fall_back_to_the_output_name_when_its_display_name_is_blank", () => {
    const nodes = [
      branchNode("router", "Smart Router", [
        { name: "category_1_result", display_name: "" },
      ]),
    ];

    const skip = getBranchSkip(
      "other",
      skipped("other", "router", ["category_1_result"]),
      nodes,
    );

    expect(skip?.outputs).toEqual(["category_1_result"]);
  });

  it("should_return_null_when_no_router_skipped_the_node", () => {
    const nodes = [branchNode("router", "If-Else", IF_ELSE_OUTPUTS)];

    expect(
      getBranchSkip(
        "out-false",
        { "out-false": { status: BuildStatus.INACTIVE } },
        nodes,
      ),
    ).toBeNull();
    expect(getBranchSkip("out-false", {}, nodes)).toBeNull();
  });

  it("should_return_null_when_the_router_node_is_gone", () => {
    expect(
      getBranchSkip("out-false", skipped("out-false", "router", []), []),
    ).toBeNull();
  });
});
