import { renderHook } from "@testing-library/react";
import { useHitlStore } from "@/stores/hitlStore";
import { useRestoreCanvasHitl } from "../use-restore-canvas-hitl";

const mockMessages = jest.fn();
const mockPending = jest.fn();

jest.mock("@/controllers/API/queries/messages", () => ({
  useGetMessagesQuery: (...args: unknown[]) => mockMessages(...args),
}));
jest.mock(
  "@/controllers/API/queries/workflows/use-get-pending-workflows",
  () => ({
    useGetPendingWorkflows: (...args: unknown[]) => mockPending(...args),
  }),
);

const card = (requestId: string, submitted?: string) => ({
  flow_id: "flow-1",
  session_id: "flow-1",
  content_blocks: [
    {
      contents: [
        {
          type: "human_input",
          request_id: requestId,
          submitted_action: submitted,
          job_id: "job-1",
        },
      ],
    },
  ],
});

const withMessages = (rows: unknown[]) =>
  mockMessages.mockReturnValue({ data: { rows: { data: rows } } });

describe("useRestoreCanvasHitl", () => {
  beforeEach(() => {
    useHitlStore.getState().clear();
    jest.clearAllMocks();
  });

  it("arms the badge when an unanswered card is still pending", () => {
    withMessages([card("Agent-x:job-1")]);
    mockPending.mockReturnValue({
      data: [{ request_id: "Agent-x:job-1" }],
    });
    renderHook(() => useRestoreCanvasHitl("flow-1"));
    expect(useHitlStore.getState().pending?.nodeId).toBe("Agent-x");
  });

  it("arms the badge from the pending list even when the messages query is stale (Bug 1)", () => {
    // The pending list (polled every 5s) is the source of truth and carries the full card; the
    // messages query is not polled, so during a live run it lags and has no card yet. The badge
    // must still arm from the pending list — otherwise the 5s poll clears it "after a while".
    withMessages([]);
    mockPending.mockReturnValue({
      data: [
        {
          request_id: "HumanInput-7DnY5:job-1",
          job_id: "job-1",
          flow_id: "flow-1",
          session_id: null,
          kind: "node_input",
          prompt: "Approve?",
          options: [{ action_id: "approve", label: "Approve" }],
          allowed_decisions: ["approve", "reject"],
        },
      ],
    });
    renderHook(() => useRestoreCanvasHitl("flow-1"));
    expect(useHitlStore.getState().pending?.nodeId).toBe("HumanInput-7DnY5");
    expect(useHitlStore.getState().pending?.content.prompt).toBe("Approve?");
  });

  it("does NOT arm (and clears) when the card's job is no longer pending", () => {
    useHitlStore.getState().setPending({
      nodeId: "stale",
      content: { request_id: "stale:job", type: "human_input" } as never,
    });
    withMessages([card("Agent-x:job-1")]);
    mockPending.mockReturnValue({ data: [] });
    renderHook(() => useRestoreCanvasHitl("flow-1"));
    expect(useHitlStore.getState().pending).toBeNull();
  });

  it("waits (no clear) while the pending list is still loading", () => {
    useHitlStore.getState().setPending({
      nodeId: "live",
      content: { request_id: "live:job", type: "human_input" } as never,
    });
    withMessages([card("Agent-x:job-1")]);
    mockPending.mockReturnValue({ data: undefined });
    renderHook(() => useRestoreCanvasHitl("flow-1"));
    expect(useHitlStore.getState().pending?.nodeId).toBe("live");
  });
});
