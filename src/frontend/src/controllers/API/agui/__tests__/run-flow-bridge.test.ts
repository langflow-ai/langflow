/**
 * Tests for the AG-UI bridge event dispatcher.
 *
 * The handler is extracted so the terminal-event contract is unit-testable
 * without standing up a real flowStore or a fake long-lived SSE stream:
 * RUN_FINISHED and RUN_ERROR must return ``true`` so the subscribe wrapper
 * tears the subscription down. STATE_DELTA, RUN_STARTED, and CUSTOM must
 * return ``false`` so the run keeps streaming.
 */

import { type BaseEvent, EventType } from "@ag-ui/client";
import {
  type BridgeContext,
  handleAGUIEvent,
} from "@/controllers/API/agui/run-flow-bridge";

function makeRecordingContext() {
  const calls: string[] = [];
  const ctx: BridgeContext = {
    setRunId: (runId) => calls.push(`setRunId:${runId}`),
    applyDelta: (ops) => calls.push(`applyDelta:${ops.length}`),
    handleCustomEvent: (eventType) => calls.push(`custom:${eventType}`),
    onFinished: () => calls.push("finished"),
    onError: (message) => calls.push(`error:${message}`),
  };
  return { ctx, calls };
}

describe("handleAGUIEvent terminal contract", () => {
  it("returns true for RUN_FINISHED and invokes onFinished", () => {
    const { ctx, calls } = makeRecordingContext();

    const terminal = handleAGUIEvent(
      { type: EventType.RUN_FINISHED } as BaseEvent,
      ctx,
    );

    expect(terminal).toBe(true);
    expect(calls).toEqual(["finished"]);
  });

  it("returns true for RUN_ERROR and surfaces the error message", () => {
    const { ctx, calls } = makeRecordingContext();

    const terminal = handleAGUIEvent(
      { type: EventType.RUN_ERROR, message: "boom" } as unknown as BaseEvent,
      ctx,
    );

    expect(terminal).toBe(true);
    expect(calls).toEqual(["error:boom"]);
  });

  it("returns true for RUN_ERROR with no message, falling back to a default", () => {
    const { ctx, calls } = makeRecordingContext();

    const terminal = handleAGUIEvent(
      { type: EventType.RUN_ERROR } as BaseEvent,
      ctx,
    );

    expect(terminal).toBe(true);
    expect(calls).toEqual(["error:Unknown run error"]);
  });
});

describe("handleAGUIEvent non-terminal contract", () => {
  it("returns false for RUN_STARTED and propagates the runId", () => {
    const { ctx, calls } = makeRecordingContext();

    const terminal = handleAGUIEvent(
      { type: EventType.RUN_STARTED, runId: "r1" } as unknown as BaseEvent,
      ctx,
    );

    expect(terminal).toBe(false);
    expect(calls).toEqual(["setRunId:r1"]);
  });

  it("returns false for RUN_STARTED with no runId, leaving setRunId untouched", () => {
    const { ctx, calls } = makeRecordingContext();

    const terminal = handleAGUIEvent(
      { type: EventType.RUN_STARTED } as BaseEvent,
      ctx,
    );

    expect(terminal).toBe(false);
    expect(calls).toEqual([]);
  });

  it("returns false for STATE_DELTA and forwards the patch ops", () => {
    const { ctx, calls } = makeRecordingContext();

    const terminal = handleAGUIEvent(
      {
        type: EventType.STATE_DELTA,
        delta: [
          { op: "add", path: "/nodes/a", value: {} },
          { op: "add", path: "/nodes/b", value: {} },
        ],
      } as unknown as BaseEvent,
      ctx,
    );

    expect(terminal).toBe(false);
    expect(calls).toEqual(["applyDelta:2"]);
  });

  it("returns false for CUSTOM(langflow.event) and forwards the event type", () => {
    const { ctx, calls } = makeRecordingContext();

    const terminal = handleAGUIEvent(
      {
        type: EventType.CUSTOM,
        name: "langflow.event",
        value: { event_type: "add_message", data: { id: "m1" } },
      } as unknown as BaseEvent,
      ctx,
    );

    expect(terminal).toBe(false);
    expect(calls).toEqual(["custom:add_message"]);
  });

  it("returns false for CUSTOM with a foreign name and skips the handler", () => {
    const { ctx, calls } = makeRecordingContext();

    const terminal = handleAGUIEvent(
      {
        type: EventType.CUSTOM,
        name: "some.other",
        value: { event_type: "add_message", data: {} },
      } as unknown as BaseEvent,
      ctx,
    );

    expect(terminal).toBe(false);
    expect(calls).toEqual([]);
  });
});
