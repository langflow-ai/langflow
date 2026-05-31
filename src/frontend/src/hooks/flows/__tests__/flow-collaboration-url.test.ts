import { buildFlowCollaborationWebSocketUrl } from "../flow-collaboration-url";

describe("buildFlowCollaborationWebSocketUrl", () => {
  it("should build a websocket URL for the flow collab endpoint", () => {
    const url = buildFlowCollaborationWebSocketUrl("abc-123");

    expect(url).toMatch(/^wss?:\/\//);
    expect(url).toMatch(/\/api\/v1\/flows\/abc-123\/collab$/);
  });
});
