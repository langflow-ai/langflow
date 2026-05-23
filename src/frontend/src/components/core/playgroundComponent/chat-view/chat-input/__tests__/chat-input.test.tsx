import { render } from "@testing-library/react";
import React from "react";

// ---------------------------------------------------------------------------
// Stores & hooks — mocked at module boundary so ChatInput renders in isolation.
// ---------------------------------------------------------------------------

let activeSessionId: string | null = null;
jest.mock("@/stores/sessionManagerStore", () => ({
  useSessionManagerStore: (selector: any) =>
    selector({ activeSessionId, setActiveSessionId: jest.fn() }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: any) => selector({ currentFlowId: "flow-1" }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({ stopBuilding: jest.fn(), isBuilding: false }),
}));

let chatValueStoreValue = "";
jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: Object.assign(
    (selector: any) =>
      selector({
        chatValueStore: chatValueStoreValue,
        setChatValueStore: jest.fn((v: string) => {
          chatValueStoreValue = v;
        }),
        setAwaitingBotResponse: jest.fn(),
      }),
    {
      getState: () => ({
        chatValueStore: chatValueStoreValue,
        setChatValueStore: jest.fn(),
        setAwaitingBotResponse: jest.fn(),
      }),
    },
  ),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: any) => selector({ setErrorData: jest.fn() }),
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
  motion: { div: (props: any) => <div {...props} /> },
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
