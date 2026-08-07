import { act, renderHook } from "@testing-library/react";
import type { ChatMessageType } from "@/types/chat";
import { useResponseCompleteCue } from "../use-response-complete-cue";

const reply = (message: string): ChatMessageType =>
  ({ id: message, message, isSend: false }) as ChatMessageType;

const sent = (message: string): ChatMessageType =>
  ({ id: message, message, isSend: true }) as ChatMessageType;

describe("useResponseCompleteCue", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("should_stay_silent_until_a_build_settles_on_a_reply", () => {
    const { result } = renderHook(() =>
      useResponseCompleteCue(true, [sent("ask")]),
    );

    expect(result.current).toEqual({
      completedCount: 0,
      completedText: "",
      isAnnouncing: false,
    });
  });

  it("should_capture_the_reply_text_when_the_build_finishes", () => {
    const { result, rerender } = renderHook(
      ({ isBuilding, chatHistory }) =>
        useResponseCompleteCue(isBuilding, chatHistory),
      {
        initialProps: {
          isBuilding: true,
          chatHistory: [sent("ask")],
        },
      },
    );

    rerender({
      isBuilding: false,
      chatHistory: [sent("ask"), reply("the answer is 42")],
    });

    expect(result.current).toEqual({
      completedCount: 1,
      completedText: "the answer is 42",
      isAnnouncing: true,
    });
  });

  it("should_ignore_a_build_that_settles_on_a_sent_message", () => {
    const { result, rerender } = renderHook(
      ({ isBuilding, chatHistory }) =>
        useResponseCompleteCue(isBuilding, chatHistory),
      {
        initialProps: { isBuilding: true, chatHistory: [sent("ask")] },
      },
    );

    rerender({ isBuilding: false, chatHistory: [sent("ask")] });

    expect(result.current.completedCount).toBe(0);
    expect(result.current.isAnnouncing).toBe(false);
  });

  // The reply used to sit in the live region forever: still announced by a
  // screen reader long after its session was gone, and duplicating every
  // transcript string page-wide.
  it("should_retire_the_announcement_after_it_has_been_spoken", () => {
    const { result, rerender } = renderHook(
      ({ isBuilding, chatHistory }) =>
        useResponseCompleteCue(isBuilding, chatHistory),
      {
        initialProps: { isBuilding: true, chatHistory: [sent("ask")] },
      },
    );

    rerender({
      isBuilding: false,
      chatHistory: [sent("ask"), reply("the answer is 42")],
    });
    expect(result.current.isAnnouncing).toBe(true);

    act(() => {
      jest.advanceTimersByTime(2000);
    });

    expect(result.current).toEqual({
      completedCount: 1,
      completedText: "",
      isAnnouncing: false,
    });
  });

  // completedCount has to survive retirement — ResponseCompleteStatus uses its
  // parity to force a text change for back-to-back identical replies.
  it("should_keep_the_completion_counter_monotonic_across_retirements", () => {
    const { result, rerender } = renderHook(
      ({ isBuilding, chatHistory }) =>
        useResponseCompleteCue(isBuilding, chatHistory),
      {
        initialProps: { isBuilding: true, chatHistory: [sent("ask")] },
      },
    );

    rerender({
      isBuilding: false,
      chatHistory: [sent("ask"), reply("same reply")],
    });
    act(() => {
      jest.advanceTimersByTime(2000);
    });

    rerender({
      isBuilding: true,
      chatHistory: [sent("ask"), reply("same reply"), sent("again")],
    });
    rerender({
      isBuilding: false,
      chatHistory: [
        sent("ask"),
        reply("same reply"),
        sent("again"),
        reply("same reply"),
      ],
    });

    expect(result.current).toEqual({
      completedCount: 2,
      completedText: "same reply",
      isAnnouncing: true,
    });
  });
});
