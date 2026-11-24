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

const t = (key: string, options?: Record<string, unknown>) => {
  if (key === "project.ownedBy") {
    return `${options?.name} — ${options?.owner}`;
  }
  return key;
};

describe("getProjectDisplayName", () => {
  it("keeps an owned project's canonical name", () => {
    expect(getProjectDisplayName(project(), t)).toBe("Starter Project");
  });

  it("qualifies a foreign project with its owner's username", () => {
    expect(
      getProjectDisplayName(
        project({ is_owner: false, owner_username: "other-user" }),
        t,
      ),
    ).toBe("Starter Project — other-user");
  });

  it("keeps the canonical name when owner metadata is missing", () => {
    expect(
      getProjectDisplayName(
        project({ is_owner: false, owner_username: null, id: "foreign-id" }),
        t,
      ),
    ).toBe("Starter Project");
  });
});

describe("getDefaultProjectId", () => {
  it("returns undefined when no projects are visible", () => {
    expect(getDefaultProjectId([], "Starter Project")).toBeUndefined();
  });

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

  it("preserves name-based default selection when ownership metadata is absent", () => {
    const projects = [
      project({ id: "first-project", name: "My Project", is_owner: undefined }),
      project({ id: "default-project", is_owner: undefined }),
    ];

    expect(getDefaultProjectId(projects, "Starter Project")).toBe(
      "default-project",
    );
  });
});
