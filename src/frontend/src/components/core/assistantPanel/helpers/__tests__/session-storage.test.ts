import type {
  AssistantMessage,
  InProgressBuildTask,
} from "../../assistant-panel.types";
import { deserializeMessages, serializeMessages } from "../session-storage";

const inProgressTask: InProgressBuildTask = {
  tool: "add_component",
  label: "Adding component...",
  componentType: "ChatInput",
  receivedAt: 1234567890,
};

function makeMessage(
  overrides: Partial<AssistantMessage> = {},
): AssistantMessage {
  return {
    id: "msg-1",
    role: "assistant",
    content: "working on it",
    timestamp: new Date("2026-07-08T12:00:00.000Z"),
    ...overrides,
  };
}

describe("serializeMessages", () => {
  it("should strip the transient inProgressTask from a streaming message", () => {
    const serialized = serializeMessages([
      makeMessage({ status: "streaming", inProgressTask }),
    ]);

    expect(serialized[0].inProgressTask).toBeUndefined();
    // Streaming still becomes cancelled on save.
    expect(serialized[0].status).toBe("cancelled");
  });

  it("should strip inProgressTask from a complete message", () => {
    const serialized = serializeMessages([
      makeMessage({ status: "complete", inProgressTask }),
    ]);

    expect(serialized[0].inProgressTask).toBeUndefined();
  });

  it("should keep inProgressTask on an error message (frozen where-it-stopped row)", () => {
    const serialized = serializeMessages([
      makeMessage({ status: "error", inProgressTask, error: "boom" }),
    ]);

    expect(serialized[0].inProgressTask).toEqual(inProgressTask);
    expect(serialized[0].status).toBe("error");
  });

  it("round-trips an error message with its inProgressTask intact", () => {
    const serialized = serializeMessages([
      makeMessage({ status: "error", inProgressTask }),
    ]);
    const restored = deserializeMessages(serialized);

    expect(restored[0].inProgressTask).toEqual(inProgressTask);
    expect(restored[0].timestamp).toEqual(new Date("2026-07-08T12:00:00.000Z"));
  });

  it("round-trips a streaming message without resurrecting the spinner", () => {
    const serialized = serializeMessages([
      makeMessage({ status: "streaming", inProgressTask }),
    ]);
    const restored = deserializeMessages(serialized);

    expect(restored[0].inProgressTask).toBeUndefined();
    expect(restored[0].status).toBe("cancelled");
  });

  it("should strip the flowProposalSnapshot canvas clone from applied proposals", () => {
    const serialized = serializeMessages([
      makeMessage({
        status: "complete",
        flowProposalStatus: "applied",
        flowProposalSnapshot: {
          nodes: [{ id: "node-1" }],
          edges: [{ id: "edge-1" }],
        },
      }),
    ]);

    expect(serialized[0]).not.toHaveProperty("flowProposalSnapshot");
    // The proposal state itself still persists so the card renders on restore.
    expect(serialized[0].flowProposalStatus).toBe("applied");
  });
});
