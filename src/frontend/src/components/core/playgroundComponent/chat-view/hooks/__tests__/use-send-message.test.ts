import { act, renderHook, waitFor } from "@testing-library/react";
import { ReadableStream } from "stream/web";
import { queryClient } from "@/contexts";
import { api } from "@/controllers/API/api";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType } from "@/types/flow";
import type { Message } from "@/types/messages";
import { useSendMessage } from "../use-send-message";

const messagesKey = [
  "useGetMessagesQuery",
  { id: "flow-1", session_id: "session-1" },
];

function acknowledgedResponse(text: string, terminalType = "RUN_ERROR") {
  const savedMessage: Message = {
    id: "message-1",
    flow_id: "flow-1",
    session_id: "session-1",
    text,
    sender: "User",
    sender_name: "User",
    timestamp: new Date().toISOString(),
    files: [],
    edit: false,
    background_color: "",
    text_color: "",
  };
  const events = [
    { type: "RUN_STARTED", threadId: "session-1", runId: "run-1" },
    {
      type: "CUSTOM",
      name: "langflow.event",
      value: { event_type: "add_message", data: savedMessage },
    },
    {
      type: terminalType,
      threadId: "session-1",
      runId: "run-1",
      message: "Provider unavailable",
    },
  ];
  return {
    savedMessage,
    response: {
      ok: true,
      status: 200,
      headers: { get: () => "text/event-stream" },
      body: new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode(
              events
                .map((event) => `data: ${JSON.stringify(event)}\n\n`)
                .join(""),
            ),
          );
          controller.close();
        },
      }),
    },
  };
}
const chatInput: AllNodeType = {
  id: "ChatInput-1",
  type: "genericNode",
  position: { x: 0, y: 0 },
  data: {
    id: "ChatInput-1",
    type: "ChatInput",
    node: {
      display_name: "Chat Input",
      template: {},
      description: "",
      documentation: "",
    },
  },
};

beforeEach(() => {
  jest.spyOn(console, "error").mockImplementation(() => {});
  queryClient.clear();
  queryClient.setQueryData(messagesKey, []);
  useFlowsManagerStore.setState({
    currentFlowId: "flow-1",
    currentFlow: {
      id: "flow-1",
      name: "Test flow",
      description: "",
      data: {
        nodes: [chatInput],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
      },
    },
  });
  useFlowStore.setState({
    nodes: [chatInput],
    edges: [],
    playgroundPage: true,
    isBuilding: false,
    buildInfo: null,
    flowBuildStatus: {},
  });
  useAlertStore.setState({
    errorData: { title: "", list: [] },
    notificationList: [],
    tempNotificationList: [],
  });
});

it("reports a maintenance refusal before a background run starts", async () => {
  useFlowStore.setState({
    nodes: [
      chatInput,
      {
        ...chatInput,
        id: "HumanInput-1",
        data: { ...chatInput.data, id: "HumanInput-1", type: "HumanInput" },
      },
    ],
  });
  jest.spyOn(api, "post").mockRejectedValue({
    response: {
      status: 503,
      data: { detail: "This instance is in maintenance mode." },
    },
  });
  const { result } = renderHook(() =>
    useSendMessage({ sessionId: "session-1" }),
  );

  await act(async () => {
    await expect(
      result.current.sendMessage({ inputValue: "Keep this draft" }),
    ).rejects.toBeDefined();
  });

  expect(queryClient.getQueryData<Message[]>(messagesKey)).toEqual([]);
  expect(useFlowStore.getState().isBuilding).toBe(false);
  expect(useAlertStore.getState().errorData.list).toEqual([
    "This instance is in maintenance mode.",
  ]);
});

it("preserves Stop behavior without reporting a failed send", async () => {
  global.fetch = jest.fn().mockImplementation(
    (_url, options) =>
      new Promise((_resolve, reject) => {
        options.signal.addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError")),
        );
      }),
  );
  const { result } = renderHook(() =>
    useSendMessage({ sessionId: "session-1" }),
  );
  let sending: Promise<void>;
  act(() => {
    sending = result.current.sendMessage({ inputValue: "Stop this run" });
  });
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());

  await act(async () => {
    useFlowStore.getState().stopBuilding();
    await expect(sending).resolves.toBeUndefined();
  });

  expect(useFlowStore.getState().isBuilding).toBe(false);
  expect(queryClient.getQueryData<Message[]>(messagesKey)).toEqual([
    expect.objectContaining({ id: null, text: "Stop this run" }),
  ]);
  expect(useAlertStore.getState().errorData.title).not.toBe(
    "Workflow run failed",
  );
});

it.each([
  ["Stop this run", true],
  ["A different message", true],
  ["Stop this run", false],
])(
  "handles a send after Stop with text %s and acknowledgement %s",
  async (text, acknowledged) => {
    const { savedMessage, response } = acknowledgedResponse(text);
    global.fetch = jest
      .fn()
      .mockImplementationOnce(
        (_url, options) =>
          new Promise((_resolve, reject) => {
            options.signal.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            );
          }),
      )
      .mockResolvedValueOnce(
        acknowledged
          ? response
          : {
              ok: false,
              status: 503,
              statusText: "Service Unavailable",
              headers: { get: () => "application/json" },
              text: async () =>
                JSON.stringify({
                  detail: "This instance is in maintenance mode.",
                }),
            },
      );
    const { result } = renderHook(() =>
      useSendMessage({ sessionId: "session-1" }),
    );
    let sending: Promise<void>;
    act(() => {
      sending = result.current.sendMessage({ inputValue: "Stop this run" });
    });
    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    await act(async () => {
      useFlowStore.getState().stopBuilding();
      await sending;
    });

    await act(async () => {
      const nextSend = result.current.sendMessage({ inputValue: text });
      if (acknowledged) {
        await expect(nextSend).resolves.toBeUndefined();
      } else {
        await expect(nextSend).rejects.toThrow();
      }
    });

    expect(queryClient.getQueryData<Message[]>(messagesKey)).toEqual([
      expect.objectContaining({ id: null, text: "Stop this run" }),
      ...(acknowledged ? [savedMessage] : []),
    ]);
    expect(useAlertStore.getState().errorData.list?.join(" ")).toContain(
      acknowledged ? "Provider unavailable" : "maintenance",
    );
  },
);

afterEach(() => {
  jest.restoreAllMocks();
  queryClient.clear();
});

it("preserves the detailed validation error when the flow cannot run", async () => {
  useFlowStore.setState({ nodes: [] });
  const { result } = renderHook(() =>
    useSendMessage({ sessionId: "session-1" }),
  );

  await act(async () => {
    await expect(
      result.current.sendMessage({ inputValue: "Keep this draft" }),
    ).rejects.toThrow("Invalid components");
  });

  expect(useAlertStore.getState().errorData.list).toEqual([
    "No components found in the flow. Please add at least one component to the flow.",
  ]);
  expect(queryClient.getQueryData<Message[]>(messagesKey)).toEqual([]);
});

it.each([true, false])(
  "removes an unsent message during maintenance with cached history %s",
  async (hasHistory) => {
    if (!hasHistory) queryClient.removeQueries({ queryKey: messagesKey });
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
      headers: { get: () => "application/json" },
      text: async () =>
        JSON.stringify({ detail: "This instance is in maintenance mode." }),
    });
    const { result } = renderHook(() =>
      useSendMessage({ sessionId: "session-1" }),
    );

    await act(async () => {
      await expect(
        result.current.sendMessage({ inputValue: "Do not lose this draft" }),
      ).rejects.toThrow();
    });

    expect(queryClient.getQueryData<Message[]>(messagesKey)).toEqual([]);
    expect(useFlowStore.getState().isBuilding).toBe(false);
    expect(useAlertStore.getState().errorData.list?.join(" ")).toContain(
      "maintenance",
    );
  },
);

it.each([
  ["RUN_FINISHED", false],
  ["RUN_ERROR", false],
  ["RUN_ERROR", true],
])(
  "keeps the received message after %s with background mode %s",
  async (terminalType, background) => {
    if (background) {
      useFlowStore.setState({
        nodes: [
          chatInput,
          {
            ...chatInput,
            id: "HumanInput-1",
            data: { ...chatInput.data, id: "HumanInput-1", type: "HumanInput" },
          },
        ],
      });
      jest.spyOn(api, "post").mockResolvedValue({ data: { job_id: "run-1" } });
    }
    const { savedMessage, response } = acknowledgedResponse(
      "Received by the server",
      terminalType,
    );
    global.fetch = jest.fn().mockResolvedValue(response);
    const { result } = renderHook(() =>
      useSendMessage({ sessionId: "session-1" }),
    );

    await act(async () => {
      await expect(
        result.current.sendMessage({ inputValue: savedMessage.text }),
      ).resolves.toBeUndefined();
    });

    expect(queryClient.getQueryData<Message[]>(messagesKey)).toEqual([
      savedMessage,
    ]);
    expect(useFlowStore.getState().isBuilding).toBe(false);
  },
);
