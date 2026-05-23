import { render } from "@testing-library/react";
import React from "react";

// ---------------------------------------------------------------------------
// Stores & hooks — mocked at module boundary so ChatInput renders in isolation.
// ---------------------------------------------------------------------------

// Generic Zustand selector type local to the test mocks. Avoids `any`
// while remaining permissive enough for ad-hoc state shapes.
type Selector<TState, TResult> = (state: TState) => TResult;

let activeSessionId: string | null = null;
type SessionManagerState = {
  activeSessionId: string | null;
  setActiveSessionId: jest.Mock;
};
jest.mock("@/stores/sessionManagerStore", () => ({
  useSessionManagerStore: <TResult,>(
    selector: Selector<SessionManagerState, TResult>,
  ) => selector({ activeSessionId, setActiveSessionId: jest.fn() }),
}));

type FlowsManagerState = { currentFlowId: string };
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: <TResult,>(selector: Selector<FlowsManagerState, TResult>) =>
    selector({ currentFlowId: "flow-1" }),
}));

type FlowStoreState = { stopBuilding: jest.Mock; isBuilding: boolean };
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: <TResult,>(selector: Selector<FlowStoreState, TResult>) =>
    selector({ stopBuilding: jest.fn(), isBuilding: false }),
}));

let chatValueStoreValue = "";
type UtilityState = {
  chatValueStore: string;
  setChatValueStore: jest.Mock;
  setAwaitingBotResponse: jest.Mock;
};
jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: Object.assign(
    <TResult,>(selector: Selector<UtilityState, TResult>) =>
      selector({
        chatValueStore: chatValueStoreValue,
        setChatValueStore: jest.fn((v: string) => {
          chatValueStoreValue = v;
        }),
        setAwaitingBotResponse: jest.fn(),
      }),
    {
      getState: (): UtilityState => ({
        chatValueStore: chatValueStoreValue,
        setChatValueStore: jest.fn(),
        setAwaitingBotResponse: jest.fn(),
      }),
    },
  ),
}));

type AlertState = { setErrorData: jest.Mock };
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: <TResult,>(selector: Selector<AlertState, TResult>) =>
    selector({ setErrorData: jest.fn() }),
}));

jest.mock("@/shared/hooks/use-chat-file-upload", () => ({
  useChatFileUpload: () => ({ handleFileChange: jest.fn() }),
}));

jest.mock("../hooks/use-audio-recording", () => ({
  useAudioRecording: () => ({
    state: { status: "idle" },
    startRecording: jest.fn(),
    stopRecording: jest.fn(),
    isSupported: false,
  }),
}));

const focusMock = jest.fn();
jest.mock("../components/input-wrapper", () => ({
  __esModule: true,
  default: ({
    inputRef,
  }: {
    inputRef: React.RefObject<HTMLTextAreaElement>;
  }) => (
    <textarea
      ref={(el) => {
        if (el && inputRef) {
          (inputRef as React.MutableRefObject<HTMLTextAreaElement>).current =
            el;
          el.focus = focusMock;
        }
      }}
      data-testid="chat-textarea"
    />
  ),
}));

jest.mock("../components/no-input", () => ({
  __esModule: true,
  default: () => <div data-testid="chat-noinput" />,
}));

jest.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  motion: {
    div: (props: React.HTMLAttributes<HTMLDivElement>) => <div {...props} />,
  },
}));

import ChatInput from "../chat-input";

const flushRaf = async () => {
  await new Promise((r) => requestAnimationFrame(r));
};

const baseProps = {
  noInput: false,
  files: [],
  setFiles: jest.fn(),
  isDragging: false,
  sendMessage: jest.fn(),
  playgroundPage: true,
};

describe("ChatInput — auto-focus on session change", () => {
  beforeEach(() => {
    focusMock.mockReset();
    activeSessionId = null;
    chatValueStoreValue = "";
  });

  it("does not focus when there is no active session yet", async () => {
    render(<ChatInput {...baseProps} />);
    await flushRaf();
    expect(focusMock).not.toHaveBeenCalled();
  });

  it("focuses the textarea once on mount when an active session exists", async () => {
    activeSessionId = "flow-1";
    render(<ChatInput {...baseProps} />);
    await flushRaf();
    expect(focusMock).toHaveBeenCalledTimes(1);
  });

  it("re-focuses the textarea when the active session changes", async () => {
    activeSessionId = "flow-1";
    const { rerender } = render(<ChatInput {...baseProps} />);
    await flushRaf();
    expect(focusMock).toHaveBeenCalledTimes(1);

    activeSessionId = "New Chat 0";
    rerender(<ChatInput {...baseProps} />);
    await flushRaf();
    expect(focusMock).toHaveBeenCalledTimes(2);
  });

  it("does not focus when noInput is true (textarea is not rendered)", async () => {
    activeSessionId = "flow-1";
    render(<ChatInput {...baseProps} noInput />);
    await flushRaf();
    expect(focusMock).not.toHaveBeenCalled();
  });

  it("cancels a pending focus when the component unmounts before rAF fires", async () => {
    activeSessionId = "flow-1";
    const { unmount } = render(<ChatInput {...baseProps} />);
    unmount();
    await flushRaf();
    expect(focusMock).not.toHaveBeenCalled();
  });

  it("does not re-fire focus when the active session stays the same across renders", async () => {
    activeSessionId = "flow-1";
    const { rerender } = render(<ChatInput {...baseProps} />);
    await flushRaf();
    expect(focusMock).toHaveBeenCalledTimes(1);

    rerender(<ChatInput {...baseProps} />);
    await flushRaf();
    expect(focusMock).toHaveBeenCalledTimes(1);
  });
});
