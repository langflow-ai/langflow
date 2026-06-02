import {
  buildSelectionIndexesWithLocal,
  isNodeSelectionHostedInChrome,
  resolveNodeCollaborationParticipants,
} from "../collaboration-node-participants";

describe("collaboration-node-participants", () => {
  it("merges the current user into the local node selection", () => {
    const indexes = buildSelectionIndexesWithLocal({
      selectionIndexes: {
        byNodeId: new Map([
          [
            "node-1",
            [
              {
                user_id: "remote-user",
                username: "remote",
                profile_image: null,
                isCurrentUser: false,
                color: "#ff0000",
              },
            ],
          ],
        ]),
        byEdgeId: new Map(),
      },
      betaEnabled: true,
      userData: {
        id: "local-user",
        username: "me",
        profile_image: null,
      },
      localSelection: { kind: "node", id: "node-1" },
      rosterUserIds: ["local-user", "remote-user"],
    });

    const participants = resolveNodeCollaborationParticipants(
      "node-1",
      indexes.byNodeId,
    );

    expect(participants).toHaveLength(2);
    expect(participants[0]?.user_id).toBe("local-user");
    expect(participants[0]?.isCurrentUser).toBe(true);
  });

  it("detects when selection chrome is hosted on the node", () => {
    expect(
      isNodeSelectionHostedInChrome("node-1", {
        kind: "node",
        id: "node-1",
      }),
    ).toBe(true);
    expect(
      isNodeSelectionHostedInChrome("node-1", {
        kind: "node",
        id: "node-2",
      }),
    ).toBe(false);
    expect(isNodeSelectionHostedInChrome("node-1", null)).toBe(false);
  });
});
