import { act, renderHook } from "@testing-library/react";

import { useAssistantChat } from "../use-assistant-chat";

/**
 * The `/iterations N` command must be handled CLIENT-side.
 *
 * The backend accepts `iterations_limit`, but until the client parses the command,
 * persists it, and puts it on the request body, typing `/iterations 60` is just an
 * ordinary prompt sent to the LLM — the budget never changes.
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

jest.mock("@/stores/assistantManagerStore", () => {
  const state = { setAssistantSidebarOpen: jest.fn() };
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

describe("/iterations command", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    mockPostAssistStream.mockImplementation(async () => {});
  });

  it("should_not_send_the_command_to_the_backend_as_a_prompt", async () => {
    const { result } = renderHook(() => useAssistantChat());

    await act(async () => {
      await result.current.handleSend("/iterations 60", TEST_MODEL);
    });

    expect(mockPostAssistStream).not.toHaveBeenCalled();
    const reply = result.current.messages.at(-1);
    expect(reply?.role).toBe("assistant");
    expect(reply?.content).toContain("60");
  });

  it("should_send_the_configured_budget_on_the_next_request", async () => {
    const { result } = renderHook(() => useAssistantChat());

    await act(async () => {
      await result.current.handleSend("/iterations 60", TEST_MODEL);
    });
    await act(async () => {
      await result.current.handleSend("build a flow", TEST_MODEL);
    });

    expect(mockPostAssistStream).toHaveBeenCalledTimes(1);
    expect(mockPostAssistStream.mock.calls[0][0]).toMatchObject({
      input_value: "build a flow",
      iterations_limit: 60,
    });
  });

  it("should_omit_iterations_limit_when_unset_so_the_flow_default_stands", async () => {
    const { result } = renderHook(() => useAssistantChat());

    await act(async () => {
      await result.current.handleSend("build a flow", TEST_MODEL);
    });

    expect(
      mockPostAssistStream.mock.calls[0][0].iterations_limit,
    ).toBeUndefined();
  });

  it("should_reset_to_the_default_on_/iterations_off", async () => {
    const { result } = renderHook(() => useAssistantChat());

    await act(async () => {
      await result.current.handleSend("/iterations 60", TEST_MODEL);
    });
    await act(async () => {
      await result.current.handleSend("/iterations off", TEST_MODEL);
    });
    await act(async () => {
      await result.current.handleSend("build a flow", TEST_MODEL);
    });

    expect(
      mockPostAssistStream.mock.calls[0][0].iterations_limit,
    ).toBeUndefined();
  });

  it("should_reject_an_out_of_range_budget_without_changing_it", async () => {
    const { result } = renderHook(() => useAssistantChat());

    await act(async () => {
      await result.current.handleSend("/iterations 9999", TEST_MODEL);
    });

    // Rejected inline; the command never reaches the backend.
    expect(result.current.messages.at(-1)?.content).toContain("Invalid");
    expect(mockPostAssistStream).not.toHaveBeenCalled();

    await act(async () => {
      await result.current.handleSend("build a flow", TEST_MODEL);
    });

    // ...and the budget was left untouched, so the flow default still stands.
    expect(
      mockPostAssistStream.mock.calls[0][0].iterations_limit,
    ).toBeUndefined();
  });

  it("should_treat_a_prompt_that_merely_starts_with_the_token_as_a_real_prompt", async () => {
    const { result } = renderHook(() => useAssistantChat());

    await act(async () => {
      await result.current.handleSend("/iterationsfoo please", TEST_MODEL);
    });

    expect(mockPostAssistStream).toHaveBeenCalled();
  });
});
