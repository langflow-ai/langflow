import { act, renderHook, waitFor } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockPostExecution = jest.fn();
const mockGetExecution = jest.fn();

jest.mock(
  "@/controllers/API/queries/deployments/use-post-deployment-execution",
  () => ({
    usePostDeploymentExecution: () => ({ mutateAsync: mockPostExecution }),
  }),
);

jest.mock(
  "@/controllers/API/queries/deployments/use-get-deployment-execution",
  () => ({
    useGetDeploymentExecution: () => ({ mutateAsync: mockGetExecution }),
  }),
);

import { useDeploymentChat } from "../use-deployment-chat";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Make a postExecution response with the given provider_data overrides. */
const makePostResponse = (
  providerDataOverrides: Record<string, unknown> = {},
) => ({
  provider_data: {
    execution_id: "exec-1",
    status: "pending",
    ...providerDataOverrides,
  },
});

/** Make a getExecution response (defaults to completed with text content). */
const makeGetResponse = (
  providerDataOverrides: Record<string, unknown> = {},
) => ({
  provider_data: {
    execution_id: "exec-1",
    status: "completed",
    result: {
      data: {
        message: {
          content: [{ type: "text", text: "Hello back!" }],
        },
      },
    },
    ...providerDataOverrides,
  },
});

/** Make a completed getExecution response with no result (falls back to status string). */
const makePendingGetResponse = () =>
  makeGetResponse({ status: "pending", result: undefined });

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useDeploymentChat", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockPostExecution.mockClear();
    mockGetExecution.mockClear();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  // -------------------------------------------------------------------------
  // Initial state
  // -------------------------------------------------------------------------

  it("initializes with empty messages and not waiting", () => {
    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    expect(result.current.messages).toEqual([]);
    expect(result.current.isWaitingForResponse).toBe(false);
  });

  // -------------------------------------------------------------------------
  // Guard conditions — sendMessage does nothing
  // -------------------------------------------------------------------------

  it("does not send a whitespace-only message", async () => {
    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("   ");
    });

    expect(mockPostExecution).not.toHaveBeenCalled();
    expect(result.current.messages).toHaveLength(0);
  });

  it("does not send an empty string", async () => {
    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("");
    });

    expect(mockPostExecution).not.toHaveBeenCalled();
  });

  it("does not send a second message while waiting for response from the first", async () => {
    mockPostExecution.mockResolvedValue(makePostResponse());
    // Keep getExecution pending forever (never resolves) so isWaitingForResponse stays true
    mockGetExecution.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    // Start first message
    act(() => {
      void result.current.sendMessage("first");
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.isWaitingForResponse).toBe(true);

    // Attempt second message
    await act(async () => {
      await result.current.sendMessage("second");
    });

    expect(mockPostExecution).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // postExecution request shape
  // -------------------------------------------------------------------------

  it("sends the message text and deployment/provider ids to postExecution", async () => {
    mockPostExecution.mockResolvedValueOnce(
      makePostResponse({ status: "completed", execution_id: null }),
    );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "my-provider", deploymentId: "my-dep" }),
    );

    await act(async () => {
      await result.current.sendMessage("hello world");
    });

    expect(mockPostExecution).toHaveBeenCalledWith(
      expect.objectContaining({
        deployment_id: "my-dep",
        provider_data: expect.objectContaining({ input: "hello world" }),
      }),
    );
  });

  // -------------------------------------------------------------------------
  // Immediate terminal — no polling
  // -------------------------------------------------------------------------

  it("handles an immediately-completed response (status=completed)", async () => {
    mockPostExecution.mockResolvedValueOnce(
      makePostResponse({
        execution_id: "exec-1",
        status: "completed",
        result: {
          data: {
            message: { content: [{ type: "text", text: "Immediate reply" }] },
          },
        },
      }),
    );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toMatchObject({
      role: "user",
      content: "hello",
    });
    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      content: "Immediate reply",
      isLoading: false,
    });
    expect(result.current.isWaitingForResponse).toBe(false);
    expect(mockGetExecution).not.toHaveBeenCalled();
  });

  it("handles an immediately-completed response via completed_at", async () => {
    mockPostExecution.mockResolvedValueOnce(
      makePostResponse({
        completed_at: "2025-01-01T00:00:00Z",
        result: {
          data: {
            message: {
              content: [{ type: "text", text: "Done via completed_at" }],
            },
          },
        },
      }),
    );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.messages[1].content).toBe("Done via completed_at");
    expect(mockGetExecution).not.toHaveBeenCalled();
  });

  it("falls back to status string when result has no text content", async () => {
    mockPostExecution.mockResolvedValueOnce(
      makePostResponse({ status: "success", result: undefined }),
    );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.messages[1].content).toBe("success");
  });

  // -------------------------------------------------------------------------
  // No execution ID returned
  // -------------------------------------------------------------------------

  it("shows error when no execution_id is returned and response is not terminal", async () => {
    mockPostExecution.mockResolvedValueOnce(
      makePostResponse({ execution_id: null, status: "pending" }),
    );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      isLoading: false,
      error: "Execution started but no execution ID was returned.",
    });
    expect(result.current.isWaitingForResponse).toBe(false);
    expect(mockGetExecution).not.toHaveBeenCalled();
  });

  // -------------------------------------------------------------------------
  // postExecution throws
  // -------------------------------------------------------------------------

  it("shows error message when postExecution throws an Error", async () => {
    mockPostExecution.mockRejectedValueOnce(new Error("Network error"));

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      isLoading: false,
      error: "Network error",
    });
    expect(result.current.isWaitingForResponse).toBe(false);
  });

  it("shows generic error when postExecution throws a non-Error value", async () => {
    mockPostExecution.mockRejectedValueOnce("unexpected string error");

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.messages[1]).toMatchObject({
      isLoading: false,
      error: "Failed to start execution",
    });
  });

  // -------------------------------------------------------------------------
  // Polling — happy path
  // -------------------------------------------------------------------------

  it("polls until terminal status then updates assistant message", async () => {
    mockPostExecution.mockResolvedValueOnce(makePostResponse());
    mockGetExecution
      .mockResolvedValueOnce(makePendingGetResponse()) // poll 1: still pending
      .mockResolvedValueOnce(makeGetResponse()); // poll 2: completed

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    act(() => {
      void result.current.sendMessage("hello");
    });

    // Flush postExecution
    await act(async () => {
      await Promise.resolve();
    });

    // Poll 1
    act(() => {
      jest.advanceTimersByTime(1500);
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockGetExecution).toHaveBeenCalledTimes(1);
    expect(result.current.isWaitingForResponse).toBe(true); // still waiting

    // Poll 2
    act(() => {
      jest.advanceTimersByTime(1500);
    });
    await act(async () => {
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.isWaitingForResponse).toBe(false);
    });

    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      content: "Hello back!",
      isLoading: false,
    });
    expect(mockGetExecution).toHaveBeenCalledTimes(2);
  });

  it("passes provider_id and execution_id to getExecution during polling", async () => {
    mockPostExecution.mockResolvedValueOnce(
      makePostResponse({ execution_id: "my-exec-id" }),
    );
    mockGetExecution.mockResolvedValueOnce(makeGetResponse());

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "my-provider", deploymentId: "d1" }),
    );

    act(() => {
      void result.current.sendMessage("hello");
    });
    await act(async () => {
      await Promise.resolve();
    });

    act(() => {
      jest.advanceTimersByTime(1500);
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockGetExecution).toHaveBeenCalledWith({
      deployment_id: "d1",
      execution_id: "my-exec-id",
    });
  });

  // -------------------------------------------------------------------------
  // Polling — failure paths
  // -------------------------------------------------------------------------

  it("shows timeout error after MAX_POLL_ATTEMPTS (30) polls all return pending", async () => {
    mockPostExecution.mockResolvedValueOnce(makePostResponse());
    // All 31 polls return pending (MAX_POLL_ATTEMPTS = 30, timeout fires at attempt 31)
    mockGetExecution.mockResolvedValue(makePendingGetResponse());

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    act(() => {
      void result.current.sendMessage("hello");
    });
    await act(async () => {
      await Promise.resolve();
    });

    // Advance through all 31 poll ticks
    for (let i = 0; i < 31; i++) {
      act(() => {
        jest.advanceTimersByTime(1500);
      });
      await act(async () => {
        await Promise.resolve();
      });
    }

    await waitFor(() => {
      expect(result.current.messages[1].error).toBe(
        "Execution timed out. Please try again.",
      );
    });

    expect(result.current.isWaitingForResponse).toBe(false);
    expect(result.current.messages[1].isLoading).toBe(false);
  });

  it("shows error when a poll call throws", async () => {
    mockPostExecution.mockResolvedValueOnce(makePostResponse());
    mockGetExecution.mockRejectedValueOnce(new Error("Poll failed"));

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    act(() => {
      void result.current.sendMessage("hello");
    });
    await act(async () => {
      await Promise.resolve();
    });

    act(() => {
      jest.advanceTimersByTime(1500);
    });
    await act(async () => {
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.messages[1].error).toBe("Poll failed");
    });

    expect(result.current.isWaitingForResponse).toBe(false);
  });

  it("shows 'Execution failed.' when execution has failed_at and no last_error", async () => {
    mockPostExecution.mockResolvedValueOnce(makePostResponse());
    mockGetExecution.mockResolvedValueOnce(
      makeGetResponse({
        failed_at: "2025-01-01T00:00:00Z",
        status: "failed",
        result: undefined,
      }),
    );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    act(() => {
      void result.current.sendMessage("hello");
    });
    await act(async () => {
      await Promise.resolve();
    });

    act(() => {
      jest.advanceTimersByTime(1500);
    });
    await act(async () => {
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.messages[1].error).toBe("Execution failed.");
    });
  });

  it("shows last_error when execution has failed_at with a specific error message", async () => {
    mockPostExecution.mockResolvedValueOnce(makePostResponse());
    mockGetExecution.mockResolvedValueOnce(
      makeGetResponse({
        failed_at: "2025-01-01T00:00:00Z",
        last_error: "Tool invocation failed: timeout",
        status: "failed",
        result: undefined,
      }),
    );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    act(() => {
      void result.current.sendMessage("hello");
    });
    await act(async () => {
      await Promise.resolve();
    });

    act(() => {
      jest.advanceTimersByTime(1500);
    });
    await act(async () => {
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.messages[1].error).toBe(
        "Tool invocation failed: timeout",
      );
    });
  });

  // -------------------------------------------------------------------------
  // Thread ID persistence
  // -------------------------------------------------------------------------

  it("extracts and persists thread_id for subsequent messages", async () => {
    const terminalResponse = {
      execution_id: null,
      thread_id: "thread-abc",
      status: "completed",
      result: {
        data: {
          message: { content: [{ type: "text", text: "Reply" }] },
        },
      },
    };

    mockPostExecution
      .mockResolvedValueOnce({ provider_data: terminalResponse })
      .mockResolvedValueOnce({ provider_data: terminalResponse });

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    // First message
    await act(async () => {
      await result.current.sendMessage("first");
    });

    // Second message — must include thread_id
    await act(async () => {
      await result.current.sendMessage("second");
    });

    expect(mockPostExecution).toHaveBeenCalledTimes(2);
    expect(mockPostExecution).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        provider_data: expect.objectContaining({ thread_id: "thread-abc" }),
      }),
    );
  });

  it("does not send thread_id on the first message", async () => {
    mockPostExecution.mockResolvedValueOnce(
      makePostResponse({ execution_id: null, status: "completed" }),
    );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(mockPostExecution).toHaveBeenCalledWith(
      expect.objectContaining({
        provider_data: expect.not.objectContaining({
          thread_id: expect.anything(),
        }),
      }),
    );
  });

  it("extracts thread_id from nested result.data.message.context.wxo_thread_id", async () => {
    mockPostExecution
      .mockResolvedValueOnce({
        provider_data: {
          execution_id: null,
          status: "completed",
          result: {
            data: {
              message: {
                context: { wxo_thread_id: "wxo-thread-xyz" },
                content: [{ type: "text", text: "Reply" }],
              },
            },
          },
        },
      })
      .mockResolvedValueOnce({
        provider_data: {
          execution_id: null,
          status: "completed",
          result: {
            data: { message: { content: [{ type: "text", text: "Second" }] } },
          },
        },
      });

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("first");
    });
    await act(async () => {
      await result.current.sendMessage("second");
    });

    expect(mockPostExecution).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        provider_data: expect.objectContaining({ thread_id: "wxo-thread-xyz" }),
      }),
    );
  });

  // -------------------------------------------------------------------------
  // Tool traces
  // -------------------------------------------------------------------------

  it("attaches tool traces to the assistant message when present", async () => {
    mockPostExecution.mockResolvedValueOnce(
      makePostResponse({
        execution_id: null,
        status: "completed",
        result: {
          data: {
            message: {
              content: [{ type: "text", text: "Done!" }],
              step_history: [
                {
                  step_details: [
                    {
                      type: "tool_calls",
                      tool_calls: [
                        { id: "c1", name: "my_tool", args: { x: 1 } },
                      ],
                    },
                    {
                      type: "tool_response",
                      tool_call_id: "c1",
                      content: "tool output",
                    },
                  ],
                },
              ],
            },
          },
        },
      }),
    );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.messages[1].toolTraces).toHaveLength(1);
    expect(result.current.messages[1].toolTraces![0]).toMatchObject({
      toolName: "my_tool",
      input: { x: 1 },
      output: "tool output",
    });
  });

  it("does not attach toolTraces when step_history is empty", async () => {
    mockPostExecution.mockResolvedValueOnce(
      makePostResponse({
        execution_id: null,
        status: "completed",
        result: {
          data: { message: { content: [{ type: "text", text: "Reply" }] } },
        },
      }),
    );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.messages[1].toolTraces).toBeUndefined();
  });

  // -------------------------------------------------------------------------
  // resetChat
  // -------------------------------------------------------------------------

  it("resetChat clears all messages and resets waiting state", async () => {
    mockPostExecution.mockResolvedValueOnce(
      makePostResponse({
        execution_id: null,
        status: "completed",
        result: {
          data: { message: { content: [{ type: "text", text: "Reply" }] } },
        },
      }),
    );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("hello");
    });
    expect(result.current.messages).toHaveLength(2);

    act(() => {
      result.current.resetChat();
    });

    expect(result.current.messages).toHaveLength(0);
    expect(result.current.isWaitingForResponse).toBe(false);
  });

  it("resetChat clears thread_id so the next message has no thread_id", async () => {
    mockPostExecution
      .mockResolvedValueOnce({
        provider_data: {
          execution_id: null,
          thread_id: "thread-to-clear",
          status: "completed",
          result: {
            data: { message: { content: [{ type: "text", text: "Reply" }] } },
          },
        },
      })
      .mockResolvedValueOnce(
        makePostResponse({ execution_id: null, status: "completed" }),
      );

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    await act(async () => {
      await result.current.sendMessage("first");
    });

    act(() => {
      result.current.resetChat();
    });

    await act(async () => {
      await result.current.sendMessage("new conversation");
    });

    expect(mockPostExecution).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        provider_data: expect.not.objectContaining({
          thread_id: expect.anything(),
        }),
      }),
    );
  });

  // -------------------------------------------------------------------------
  // User message appearance
  // -------------------------------------------------------------------------

  it("adds user and assistant (loading) messages immediately on send", async () => {
    // Use a never-resolving promise to keep the hook in loading state
    mockPostExecution.mockReturnValueOnce(new Promise(() => {}));

    const { result } = renderHook(() =>
      useDeploymentChat({ providerId: "p1", deploymentId: "d1" }),
    );

    act(() => {
      void result.current.sendMessage("hello");
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toMatchObject({
      role: "user",
      content: "hello",
    });
    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      content: "",
      isLoading: true,
    });
    expect(result.current.isWaitingForResponse).toBe(true);
  });
});
