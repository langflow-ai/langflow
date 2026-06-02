import {
  buildCollaborationSelectionOutline,
  getCollaborationUserColor,
} from "../collaboration-user-color";

describe("collaboration user colors", () => {
  it("returns a stable color for a user id", () => {
    expect(getCollaborationUserColor("user-1")).toBe(
      getCollaborationUserColor("user-1"),
    );
  });

  it("assigns distinct colors to collaborators in the same roster", () => {
    const roster = ["user-a", "user-b", "user-c"];
    const colors = roster.map((userId) =>
      getCollaborationUserColor(userId, roster),
    );

    expect(new Set(colors).size).toBe(roster.length);
  });

  it("builds stacked outlines for multiple collaborators", () => {
    expect(buildCollaborationSelectionOutline(["#3b82f6", "#f97316"])).toBe(
      "0 0 0 2px #3b82f6, 0 0 0 4px #f97316",
    );
  });
});
