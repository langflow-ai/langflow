/**
 * Drives the fetch-based durable-event consumer end to end with a mocked SSE
 * stream. The pause case is the regression that mattered: a stream that closes
 * after ``langflow.human_input_required`` (no terminal RUN_FINISHED) must still
 * inject the card and clear the building spinner.
 */

import { ReadableStream as NodeReadableStream } from "stream/web";
import {
  TextDecoder as NodeTextDecoder,
  TextEncoder as NodeTextEncoder,
} from "util";

Object.assign(globalThis, {
  TextEncoder: globalThis.TextEncoder ?? NodeTextEncoder,
  TextDecoder: globalThis.TextDecoder ?? NodeTextDecoder,
  ReadableStream: globalThis.ReadableStream ?? NodeReadableStream,
});

const addMessage = jest.fn();
const setIsBuilding = jest.fn();
const setAwaitingInput = jest.fn();
const setBuildInfo = jest.fn();
const updateEdgesRunningByNodes = jest.fn();
const revertBuiltStatusFromBuilding = jest.fn();
const setErrorData = jest.fn();
let storeMessages: { id: string }[] = [];

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setIsBuilding,
      setAwaitingInput,
      setBuildInfo,
      updateEdgesRunningByNodes,
      revertBuiltStatusFromBuilding,
    }),
  },
}));
jest.mock("@/stores/messagesStore", () => ({
  useMessagesStore: {
    getState: () => ({
      addMessage,
      messages: storeMessages,
    }),
  },
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: { getState: () => ({ setErrorData }) },
}));
jest.mock(
  "@/components/core/playgroundComponent/chat-view/utils/message-event-handler",
  () => ({ handleMessageEvent: jest.fn() }),
);
const updateMessageMock = jest.fn();
jest.mock(
  "@/components/core/playgroundComponent/chat-view/utils/message-utils",
  () => ({ updateMessage: (...args: unknown[]) => updateMessageMock(...args) }),
);

import { queryClient } from "@/contexts";
import { consumeBackgroundEvents } from "@/controllers/API/agui/run-flow-bridge";

function sseStream(frames: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(`data: ${frame}\n\n`));
      }
      controller.close();
    },
  });
}

/** Emits real `data:\nid:` frames and closes WITHOUT a trailing blank line. */
function sseStreamNoTrailingBlank(
  frames: string[],
): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const body =
    frames.map((f, i) => `data: ${f}\nid: ${i + 1}`).join("\n\n") + "\n";
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(body));
      controller.close();
    },
  });
}

describe("consumeBackgroundEvents", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    storeMessages = [];
    queryClient.clear();
  });

  it("injects the card and parks awaiting-input when the run suspends", async () => {
    const humanInput = JSON.stringify({
      type: "CUSTOM",
      name: "langflow.human_input_required",
      value: {
        request_id: "HI:job-1",
        kind: "node_input",
        prompt: "Approve?",
        options: [{ action_id: "approve", label: "Approve" }],
        schema: [],
        allowed_decisions: ["approve"],
      },
    });
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      body: sseStream([
        JSON.stringify({ type: "RUN_STARTED", runId: "job-1" }),
        humanInput,
      ]),
    }) as unknown as typeof fetch;

    await consumeBackgroundEvents("job-1", { flowId: "f1", threadId: "s1" });

    expect(addMessage).toHaveBeenCalledTimes(1);
    expect(addMessage.mock.calls[0][0].id).toBe("human-input-HI:job-1");
    // The new playground reads the react-query cache, not useMessagesStore.
    expect(updateMessageMock).toHaveBeenCalledTimes(1);
    expect(updateMessageMock.mock.calls[0][0].id).toBe("human-input-HI:job-1");
    expect(setIsBuilding).toHaveBeenLastCalledWith(false);
    expect(setAwaitingInput).toHaveBeenLastCalledWith(true);
  });

  it("processes the final pause frame even when the stream closes without a trailing blank line", async () => {
    const humanInput = JSON.stringify({
      type: "CUSTOM",
      name: "langflow.human_input_required",
      value: {
        request_id: "HI:job-2",
        kind: "node_input",
        prompt: "Approve?",
        options: [{ action_id: "approve", label: "Approve" }],
        schema: [],
        allowed_decisions: ["approve"],
      },
    });
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      body: sseStreamNoTrailingBlank([
        JSON.stringify({ type: "RUN_STARTED", runId: "job-2" }),
        JSON.stringify({ type: "STATE_DELTA", delta: [] }),
        humanInput,
      ]),
    }) as unknown as typeof fetch;

    await consumeBackgroundEvents("job-2", { flowId: "f1", threadId: "s1" });

    expect(addMessage).toHaveBeenCalledTimes(1);
    expect(addMessage.mock.calls[0][0].id).toBe("human-input-HI:job-2");
    expect(setAwaitingInput).toHaveBeenLastCalledWith(true);
  });

  it("does not re-inject an already-answered pause replayed on a reattach", async () => {
    // The user already answered this pause: its card carries submitted_action in the cache.
    queryClient.setQueryData(
      ["useGetMessagesQuery", "s1"],
      [
        {
          id: "human-input-HI:job-3",
          content_blocks: [
            {
              contents: [{ type: "human_input", submitted_action: "approve" }],
            },
          ],
        },
      ],
    );
    const humanInput = JSON.stringify({
      type: "CUSTOM",
      name: "langflow.human_input_required",
      value: {
        request_id: "HI:job-3",
        kind: "node_input",
        prompt: "Approve?",
        options: [],
        allowed_decisions: [],
      },
    });
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      body: sseStream([
        JSON.stringify({ type: "RUN_STARTED", runId: "job-3" }),
        humanInput,
        JSON.stringify({ type: "RUN_FINISHED" }),
      ]),
    }) as unknown as typeof fetch;

    await consumeBackgroundEvents(
      "job-3",
      { flowId: "f1", threadId: "s1" },
      undefined,
      { skipCardInjection: true },
    );

    // The replayed, already-answered pause must NOT re-add the card; the run finishes normally.
    expect(addMessage).not.toHaveBeenCalled();
    expect(updateMessageMock).not.toHaveBeenCalled();
    expect(setAwaitingInput).toHaveBeenLastCalledWith(false);
  });

  it("injects a genuinely-new second pause on a post-resume reattach", async () => {
    // Two sequential HumanInput nodes: the reattach replays the answered first pause AND the
    // genuinely-new second pause. The second card must surface even with skipCardInjection.
    queryClient.setQueryData(
      ["useGetMessagesQuery", "s1"],
      [
        {
          id: "human-input-HI1:job-4",
          content_blocks: [
            {
              contents: [{ type: "human_input", submitted_action: "approve" }],
            },
          ],
        },
      ],
    );
    const replayedAnswered = JSON.stringify({
      type: "CUSTOM",
      name: "langflow.human_input_required",
      value: { request_id: "HI1:job-4", kind: "node_input", options: [] },
    });
    const secondPause = JSON.stringify({
      type: "CUSTOM",
      name: "langflow.human_input_required",
      value: {
        request_id: "HI2:job-4",
        kind: "node_input",
        prompt: "Approve again?",
        options: [{ action_id: "approve", label: "Approve" }],
        allowed_decisions: ["approve"],
      },
    });
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      body: sseStream([
        JSON.stringify({ type: "RUN_STARTED", runId: "job-4" }),
        replayedAnswered,
        secondPause,
      ]),
    }) as unknown as typeof fetch;

    await consumeBackgroundEvents(
      "job-4",
      { flowId: "f1", threadId: "s1" },
      undefined,
      { skipCardInjection: true },
    );

    // Only the second (unanswered) pause injects its card; the first replay is skipped.
    expect(addMessage).toHaveBeenCalledTimes(1);
    expect(addMessage.mock.calls[0][0].id).toBe("human-input-HI2:job-4");
    expect(setAwaitingInput).toHaveBeenLastCalledWith(true);
  });

  it("clears awaiting-input when a resumed run reaches RUN_FINISHED", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      body: sseStream([
        JSON.stringify({ type: "RUN_STARTED", runId: "job-1" }),
        JSON.stringify({ type: "RUN_FINISHED" }),
      ]),
    }) as unknown as typeof fetch;

    await consumeBackgroundEvents("job-1", { flowId: "f1", threadId: "s1" });

    expect(setIsBuilding).toHaveBeenLastCalledWith(false);
    expect(setAwaitingInput).toHaveBeenLastCalledWith(false);
    expect(setBuildInfo).toHaveBeenCalledWith({ success: true });
  });
});
