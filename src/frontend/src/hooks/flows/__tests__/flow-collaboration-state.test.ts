import {
  applyPresenceJoined,
  applyPresenceLeft,
  applyPresenceSnapshot,
  applySelectionSnapshot,
  applySelectionUpdated,
} from "@/hooks/flows/flow-collaboration-state";

describe("flow-collaboration-state", () => {
  it("should replace the roster on presence.snapshot", () => {
    expect(
      applyPresenceSnapshot(
        [{ user_id: "old", username: "old-user" }],
        [{ user_id: "new", username: "new-user" }],
      ),
    ).toEqual([{ user_id: "new", username: "new-user" }]);
  });

  it("should add or update users on presence.joined", () => {
    expect(
      applyPresenceJoined([], {
        user_id: "user-1",
        username: "ana",
      }),
    ).toEqual([{ user_id: "user-1", username: "ana" }]);

    expect(
      applyPresenceJoined([{ user_id: "user-1", username: "old" }], {
        user_id: "user-1",
        username: "ana",
        profile_image: "Space/046-rocket.svg",
      }),
    ).toEqual([
      {
        user_id: "user-1",
        username: "ana",
        profile_image: "Space/046-rocket.svg",
      },
    ]);
  });

  it("should remove users on presence.left", () => {
    expect(
      applyPresenceLeft(
        [
          { user_id: "user-1", username: "ana" },
          { user_id: "user-2", username: "bob" },
        ],
        "user-1",
      ),
    ).toEqual([{ user_id: "user-2", username: "bob" }]);
  });

  it("should replace selections on selection.snapshot", () => {
    expect(
      applySelectionSnapshot(
        [{ user_id: "user-1", selected: { kind: "node", id: "n1" } }],
        [{ user_id: "user-2", selected: { kind: "edge", id: "e1" } }],
      ),
    ).toEqual([{ user_id: "user-2", selected: { kind: "edge", id: "e1" } }]);
  });

  it("should upsert or clear selections on selection.updated", () => {
    expect(
      applySelectionUpdated([], "user-1", { kind: "node", id: "n1" }),
    ).toEqual([{ user_id: "user-1", selected: { kind: "node", id: "n1" } }]);

    expect(
      applySelectionUpdated(
        [{ user_id: "user-1", selected: { kind: "node", id: "n1" } }],
        "user-1",
        null,
      ),
    ).toEqual([]);
  });
});
