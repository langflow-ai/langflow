import type { ProjectListType } from "@/pages/MainPage/entities";
import {
  getDefaultProjectId,
  getProjectDisplayName,
} from "../project-display-name";

const project = (
  overrides: Partial<ProjectListType> = {},
): ProjectListType => ({
  id: "project-id",
  name: "Starter Project",
  description: "",
  parent_id: "",
  flows: [],
  components: [],
  owner_username: "current-user",
  is_owner: true,
  ...overrides,
});

describe("getProjectDisplayName", () => {
  it("keeps an owned project's canonical name", () => {
    expect(getProjectDisplayName(project())).toBe("Starter Project");
  });

  it("qualifies a foreign project with its owner's username", () => {
    expect(
      getProjectDisplayName(
        project({ is_owner: false, owner_username: "other-user" }),
      ),
    ).toBe("Starter Project — other-user");
  });

  it("falls back to the project id when owner metadata is missing", () => {
    expect(
      getProjectDisplayName(
        project({ is_owner: false, owner_username: null, id: "foreign-id" }),
      ),
    ).toBe("Starter Project — foreign-id");
  });
});

describe("getDefaultProjectId", () => {
  it("selects the caller-owned default when a foreign duplicate comes first", () => {
    const projects = [
      project({
        id: "foreign-default",
        is_owner: false,
        owner_username: "other-user",
      }),
      project({ id: "own-default" }),
    ];

    expect(getDefaultProjectId(projects, "Starter Project")).toBe(
      "own-default",
    );
  });

  it("falls back to another owned project before a visible foreign project", () => {
    const projects = [
      project({
        id: "foreign-default",
        is_owner: false,
        owner_username: "other-user",
      }),
      project({ id: "own-project", name: "My Project" }),
    ];

    expect(getDefaultProjectId(projects, "Starter Project")).toBe(
      "own-project",
    );
  });
});
