import {
  applyPresenceJoined,
  applyPresenceLeft,
  applyPresenceSnapshot,
  applySelectionUpdated,
  buildCollaboratorRows,
  selectionsFromPresenceSnapshot,
} from "@/hooks/flows/flow-collaboration-state";
import type { AllNodeType, EdgeType } from "@/types/flow";

describe("flow-collaboration-state", () => {
  it("should replace the roster on presence.snapshot", () => {
    expect(
      applyPresenceSnapshot(
        [{ user_id: "old", username: "old-user" }],
        [
          {
            user_id: "new",
            username: "new-user",
            selected: { kind: "node", id: "n1" },
          },
        ],
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

  it("should derive selections from presence.snapshot users", () => {
    expect(
      selectionsFromPresenceSnapshot([
        { user_id: "user-1", username: "ana", selected: null },
        {
          user_id: "user-2",
          username: "bob",
          selected: { kind: "edge", id: "e1" },
        },
      ]),
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

  it("should build collaborator rows including the current user first", () => {
    const node = {
      id: "node-1",
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: {
        id: "node-1",
        type: "Parser",
        node: { display_name: "Parser", template: {} },
      },
    } as AllNodeType;

    expect(
      buildCollaboratorRows({
        users: [
          { user_id: "user-1", username: "ana" },
          { user_id: "user-2", username: "bob" },
        ],
        selections: [
          { user_id: "user-2", selected: { kind: "node", id: "node-1" } },
        ],
        nodes: [node],
        edges: [] as EdgeType[],
        currentUserId: "user-1",
        currentUserProfile: {
          user_id: "user-1",
          username: "ana",
        },
        localSelectionForCurrentUser: null,
      }),
    ).toEqual([
      {
        user_id: "user-1",
        username: "ana",
        profile_image: undefined,
        selected: null,
        selectionLabel: null,
        isCurrentUser: true,
        color: expect.any(String),
      },
      {
        user_id: "user-2",
        username: "bob",
        profile_image: undefined,
        selected: { kind: "node", id: "node-1" },
        selectionLabel: "Parser",
        isCurrentUser: false,
        color: expect.any(String),
      },
    ]);
  });

  it("should synthesize the current user when they are not in the presence roster yet", () => {
    expect(
      buildCollaboratorRows({
        users: [],
        selections: [],
        nodes: [],
        edges: [] as EdgeType[],
        currentUserId: "user-1",
        currentUserProfile: {
          user_id: "user-1",
          username: "ana",
          profile_image: "Space/046-rocket.svg",
        },
        localSelectionForCurrentUser: null,
      }),
    ).toEqual([
      {
        user_id: "user-1",
        username: "ana",
        profile_image: "Space/046-rocket.svg",
        selected: null,
        selectionLabel: null,
        isCurrentUser: true,
        color: expect.any(String),
      },
    ]);
  });
});
