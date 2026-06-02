import type { CollaborationCollaboratorRow } from "@/types/flow-collaboration";
import { groupCollaboratorsBySelection } from "../collaboration-selection-markers";

describe("groupCollaboratorsBySelection", () => {
  it("groups multiple collaborators on the same node", () => {
    const collaborators: CollaborationCollaboratorRow[] = [
      {
        user_id: "user-1",
        username: "ana",
        selected: { kind: "node", id: "node-1" },
        selectionLabel: "Parser",
        isCurrentUser: true,
        color: "#3b82f6",
      },
      {
        user_id: "user-2",
        username: "bob",
        selected: { kind: "node", id: "node-1" },
        selectionLabel: "Parser",
        isCurrentUser: false,
        color: "#f97316",
      },
      {
        user_id: "user-3",
        username: "carol",
        selected: { kind: "edge", id: "edge-1" },
        selectionLabel: "A → B",
        isCurrentUser: false,
        color: "#22c55e",
      },
    ];

    expect(groupCollaboratorsBySelection(collaborators)).toEqual([
      {
        targetId: "node-1",
        kind: "node",
        participants: [
          expect.objectContaining({ user_id: "user-1", isCurrentUser: true }),
          expect.objectContaining({ user_id: "user-2" }),
        ],
      },
      {
        targetId: "edge-1",
        kind: "edge",
        participants: [expect.objectContaining({ user_id: "user-3" })],
      },
    ]);
  });
});
