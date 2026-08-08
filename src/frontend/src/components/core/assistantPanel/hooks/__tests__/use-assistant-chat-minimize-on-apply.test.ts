import { act, renderHook } from "@testing-library/react";

import { useAssistantChat } from "../use-assistant-chat";

/**
 * QA: after "Add to canvas" the assistant panel must minimize automatically, so
 * the user immediately sees the flow that was just created instead of having to
 * close the panel by hand.
 *
 * Applying is the reveal moment for BOTH modes (add and replace) — each writes
 * the canvas. Dismiss does not touch the canvas, so it must leave the panel open.
 */

jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => () => {},
}));

const mockPostAssistStream = jest.fn();
jest.mock("@/controllers/API/queries/agentic", () => ({
  postAssistStream: (...args: unknown[]) => mockPostAssistStream(...args),
}));

jest.mock(
  "@/controllers/API/queries/nodes/use-post-validate-component-code",
  () => ({
    usePostValidateComponentCode: () => ({ mutateAsync: jest.fn() }),
  }),
);

jest.mock("@/hooks/use-add-component", () => ({
  useAddComponent: () => jest.fn(),
}));

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/stores/flowsManagerStore", () => {
  const fn = (selector: (state: { currentFlowId: string }) => unknown) =>
    selector({ currentFlowId: "test-flow-id" });
  fn.getState = () => ({ currentFlowId: "test-flow-id" });
  return { __esModule: true, default: fn };
});

jest.mock("@/stores/flowStore", () => {
  const state = {
    nodes: [],
    edges: [],
    setNodes: jest.fn(),
    setEdges: jest.fn(),
    paste: jest.fn(),
  };
  const fn = (selector?: (s: typeof state) => unknown) =>
    selector ? selector(state) : state;
  fn.getState = () => state;
  return { __esModule: true, default: fn };
});

const mockSetAssistantSidebarOpen = jest.fn();
jest.mock("@/stores/assistantManagerStore", () => {
  const state = {
    setAssistantSidebarOpen: (...args: unknown[]) =>
      mockSetAssistantSidebarOpen(...args),
  };
  const fn = (selector?: (s: typeof state) => unknown) =>
    selector ? selector(state) : state;
  fn.getState = () => state;
  return { __esModule: true, default: fn };
});

jest.mock("short-unique-id", () => {
  let counter = 0;
  return class ShortUniqueId {
    randomUUID() {
      counter += 1;
      return `mock-uid-${counter}`;
    }
  };
});

const TEST_MODEL = {
  id: "openai/gpt-4",
  name: "gpt-4",
  provider: "openai",
  displayName: "GPT-4",
};

const SAMPLE_FLOW = {
  name: "Test Flow",
  data: {
    nodes: [{ id: "n1" }, { id: "n2" }],
    edges: [{ id: "e1", source: "n1", target: "n2" }],
  },
};

async function proposeFlow() {
  mockPostAssistStream.mockImplementation(
    async (_req: unknown, callbacks: Record<string, Function>) => {
      callbacks.onFlowUpdate({
        event: "flow_update",
        action: "set_flow",
        flow: SAMPLE_FLOW,
      });
    },
  );
  const { result } = renderHook(() => useAssistantChat());
  await act(async () => {
    await result.current.handleSend("build a flow", TEST_MODEL);
  });
  return result;
}

describe("assistant panel minimizes after applying a flow proposal", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_minimize_the_panel_when_the_proposal_is_added_to_canvas", async () => {
    const result = await proposeFlow();
    const msg = result.current.messages[1];

    act(() => {
      result.current.handleApplyFlowProposal(msg.id, "add");
    });

    expect(mockSetAssistantSidebarOpen).toHaveBeenCalledWith(false);
  });

  it("should_minimize_the_panel_when_the_canvas_is_replaced", async () => {
    const result = await proposeFlow();
    const msg = result.current.messages[1];

    act(() => {
      result.current.handleApplyFlowProposal(msg.id, "replace");
    });

    expect(mockSetAssistantSidebarOpen).toHaveBeenCalledWith(false);
  });

  it("should_not_minimize_the_panel_when_the_proposal_is_dismissed", async () => {
    const result = await proposeFlow();
    const msg = result.current.messages[1];

    act(() => {
      result.current.handleDismissFlowProposal(msg.id);
    });

    expect(mockSetAssistantSidebarOpen).not.toHaveBeenCalled();
  });

  it("should_not_minimize_when_there_is_no_pending_proposal", async () => {
    const result = await proposeFlow();

    act(() => {
      result.current.handleApplyFlowProposal("does-not-exist", "add");
    });

    expect(mockSetAssistantSidebarOpen).not.toHaveBeenCalled();
  });
});
