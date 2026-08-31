import { renderHook } from "@testing-library/react";
import { useScopedVoiceInitialization } from "../use-scoped-voice-initialization";

describe("useScopedVoiceInitialization", () => {
  it("fails closed when no flow scope is available", () => {
    const initializeAudio = jest.fn();
    const stopRecording = jest.fn();

    renderHook(() =>
      useScopedVoiceInitialization({
        flowId: "",
        hasOpenAIAPIKey: true,
        scopedCredentialsReady: true,
        showSettingsModal: false,
        initializeAudio,
        stopRecording,
        setIsRecording: jest.fn(),
      }),
    );

    expect(initializeAudio).not.toHaveBeenCalled();
    expect(stopRecording).toHaveBeenCalledTimes(1);
  });

  it("initializes only after scoped credentials settle successfully", () => {
    const initializeAudio = jest.fn();
    const stopRecording = jest.fn();
    const setIsRecording = jest.fn();
    const callbacks = { initializeAudio, stopRecording, setIsRecording };

    const { rerender } = renderHook(
      (props: {
        flowId: string;
        hasOpenAIAPIKey: boolean;
        scopedCredentialsReady: boolean;
      }) =>
        useScopedVoiceInitialization({
          ...props,
          ...callbacks,
          showSettingsModal: false,
        }),
      {
        initialProps: {
          flowId: "flow-a",
          hasOpenAIAPIKey: false,
          scopedCredentialsReady: false,
        },
      },
    );

    expect(stopRecording).toHaveBeenCalledTimes(1);
    expect(initializeAudio).not.toHaveBeenCalled();

    rerender({
      flowId: "flow-a",
      hasOpenAIAPIKey: true,
      scopedCredentialsReady: true,
    });

    expect(setIsRecording).toHaveBeenCalledWith(true);
    expect(initializeAudio).toHaveBeenCalledTimes(1);

    rerender({
      flowId: "flow-a",
      hasOpenAIAPIKey: true,
      scopedCredentialsReady: true,
    });
    expect(initializeAudio).toHaveBeenCalledTimes(1);
  });

  it("stops during a scoped refresh and restarts only after fresh success", () => {
    const initializeAudio = jest.fn();
    const stopRecording = jest.fn();
    const setIsRecording = jest.fn();
    const callbacks = { initializeAudio, stopRecording, setIsRecording };

    const { rerender } = renderHook(
      (props: { scopedCredentialsReady: boolean }) =>
        useScopedVoiceInitialization({
          flowId: "flow-a",
          hasOpenAIAPIKey: true,
          showSettingsModal: false,
          ...props,
          ...callbacks,
        }),
      { initialProps: { scopedCredentialsReady: true } },
    );

    expect(initializeAudio).toHaveBeenCalledTimes(1);

    rerender({ scopedCredentialsReady: false });
    expect(stopRecording).toHaveBeenCalledTimes(1);

    rerender({ scopedCredentialsReady: true });
    expect(initializeAudio).toHaveBeenCalledTimes(2);
  });

  it("does not initialize refreshed credentials behind an open settings dialog", () => {
    const initializeAudio = jest.fn();
    const stopRecording = jest.fn();
    const setIsRecording = jest.fn();
    const callbacks = { initializeAudio, stopRecording, setIsRecording };

    const { rerender } = renderHook(
      (props: {
        scopedCredentialsReady: boolean;
        showSettingsModal: boolean;
      }) =>
        useScopedVoiceInitialization({
          flowId: "flow-a",
          hasOpenAIAPIKey: true,
          ...props,
          ...callbacks,
        }),
      {
        initialProps: {
          scopedCredentialsReady: false,
          showSettingsModal: true,
        },
      },
    );

    rerender({
      scopedCredentialsReady: true,
      showSettingsModal: true,
    });
    expect(initializeAudio).not.toHaveBeenCalled();

    rerender({
      scopedCredentialsReady: true,
      showSettingsModal: false,
    });
    expect(initializeAudio).toHaveBeenCalledTimes(1);
  });

  it("stops the previous flow before initializing a newly scoped flow", () => {
    const events: string[] = [];
    const initializeAudio = jest.fn(() => {
      events.push("initialize");
    });
    const stopRecording = jest.fn(() => {
      events.push("stop");
    });
    const setIsRecording = jest.fn();

    const { rerender } = renderHook(
      ({ flowId }: { flowId: string }) =>
        useScopedVoiceInitialization({
          flowId,
          hasOpenAIAPIKey: true,
          scopedCredentialsReady: true,
          showSettingsModal: false,
          initializeAudio,
          stopRecording,
          setIsRecording,
        }),
      { initialProps: { flowId: "flow-a" } },
    );

    rerender({ flowId: "flow-b" });

    expect(events).toEqual(["initialize", "stop", "initialize"]);
  });

  it("invalidates in-flight initialization and stops recording on unmount", () => {
    let isCurrent: (() => boolean) | undefined;
    const initializeAudio = jest.fn((callback: () => boolean) => {
      isCurrent = callback;
    });
    const stopRecording = jest.fn();

    const { unmount } = renderHook(() =>
      useScopedVoiceInitialization({
        flowId: "flow-a",
        hasOpenAIAPIKey: true,
        scopedCredentialsReady: true,
        showSettingsModal: false,
        initializeAudio,
        stopRecording,
        setIsRecording: jest.fn(),
      }),
    );

    expect(isCurrent?.()).toBe(true);

    unmount();

    expect(isCurrent?.()).toBe(false);
    expect(stopRecording).toHaveBeenCalledTimes(1);
  });
});
