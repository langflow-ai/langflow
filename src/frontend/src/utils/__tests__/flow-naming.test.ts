import type { FlowType } from "@/types/flow";
import { getFolderScopedDuplicateName } from "../flow-naming";

function makeFlow(partial: Partial<FlowType>): FlowType {
  return {
    id: "id",
    name: "name",
    description: "",
    data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
    ...partial,
  } as FlowType;
}

describe("getFolderScopedDuplicateName", () => {
  it("should_version_the_name_when_a_sibling_in_the_same_folder_shares_it", () => {
    const flows = [
      makeFlow({ id: "a", name: "Simple Agent", folder_id: "f1" }),
    ];
    const name = getFolderScopedDuplicateName(
      makeFlow({ id: "b", name: "Simple Agent", folder_id: "f1" }),
      flows,
      "f1",
    );
    expect(name).toBe("Simple Agent (1)");
  });

  it("should_keep_the_name_when_the_only_match_lives_in_another_folder", () => {
    const flows = [
      makeFlow({ id: "a", name: "Simple Agent", folder_id: "f2" }),
    ];
    const name = getFolderScopedDuplicateName(
      makeFlow({ id: "b", name: "Simple Agent", folder_id: "f1" }),
      flows,
      "f1",
    );
    expect(name).toBe("Simple Agent");
  });

  it("should_not_count_the_flow_itself_as_a_collision", () => {
    const flows = [
      makeFlow({ id: "b", name: "Simple Agent", folder_id: "f1" }),
    ];
    const name = getFolderScopedDuplicateName(
      makeFlow({ id: "b", name: "Simple Agent", folder_id: "f1" }),
      flows,
      "f1",
    );
    expect(name).toBe("Simple Agent");
  });
});
