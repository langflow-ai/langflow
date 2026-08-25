import type { FlowType } from "@/types/flow";
import {
  getFolderScopedDuplicateName,
  getUserScopedDuplicateName,
} from "../flow-naming";

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

describe("getUserScopedDuplicateName", () => {
  it("should_version_the_name_when_a_flow_in_another_folder_shares_it", () => {
    // The backend's ``unique_flow_name`` constraint is (user_id, name), so a
    // match in ANY folder is a real collision — folder scoping would let the
    // rename through and the PATCH would fail with "Name must be unique".
    const flows = [
      makeFlow({ id: "a", name: "Simple Agent", folder_id: "f2" }),
    ];
    const name = getUserScopedDuplicateName(
      makeFlow({ id: "b", name: "Simple Agent", folder_id: "f1" }),
      flows,
    );
    expect(name).toBe("Simple Agent (1)");
  });

  it("should_version_the_name_when_a_sibling_in_the_same_folder_shares_it", () => {
    const flows = [
      makeFlow({ id: "a", name: "Simple Agent", folder_id: "f1" }),
    ];
    const name = getUserScopedDuplicateName(
      makeFlow({ id: "b", name: "Simple Agent", folder_id: "f1" }),
      flows,
    );
    expect(name).toBe("Simple Agent (1)");
  });

  it("should_ignore_example_flows_because_they_have_no_owner", () => {
    // Starter examples are ownerless rows (user_id IS NULL) served alongside the
    // user's own flows under AUTO_LOGIN. They never collide with (user_id, name),
    // so counting them would suffix a name that is actually free.
    const example = makeFlow({
      id: "ex-1",
      name: "Simple Agent",
      folder_id: "starter",
    });
    const name = getUserScopedDuplicateName(
      makeFlow({ id: "b", name: "Simple Agent", folder_id: "f1" }),
      [example],
      [example],
    );
    expect(name).toBe("Simple Agent");
  });

  it("should_not_count_the_flow_itself_as_a_collision", () => {
    const flows = [
      makeFlow({ id: "b", name: "Simple Agent", folder_id: "f1" }),
    ];
    const name = getUserScopedDuplicateName(
      makeFlow({ id: "b", name: "Simple Agent", folder_id: "f1" }),
      flows,
    );
    expect(name).toBe("Simple Agent");
  });

  it("should_pick_the_next_free_version_when_earlier_versions_are_taken", () => {
    const flows = [
      makeFlow({ id: "a", name: "Simple Agent", folder_id: "f1" }),
      makeFlow({ id: "b", name: "Simple Agent (1)", folder_id: "f2" }),
    ];
    const name = getUserScopedDuplicateName(
      makeFlow({ id: "c", name: "Simple Agent", folder_id: "f1" }),
      flows,
    );
    expect(name).toBe("Simple Agent (2)");
  });
});
