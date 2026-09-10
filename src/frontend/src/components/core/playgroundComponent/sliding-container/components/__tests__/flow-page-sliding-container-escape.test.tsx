import { fireEvent, render, screen } from "@testing-library/react";
import { FlowPageSlidingContainerContent } from "../flow-page-sliding-container";

jest.mock("use-stick-to-bottom", () => {
  const StickToBottom = ({ children }: { children?: React.ReactNode }) => (
    <>{children}</>
  );
  StickToBottom.Content = ({ children }: { children?: React.ReactNode }) => (
    <>{children}</>
  );
  return {
    StickToBottom,
    useStickToBottom: () => ({ scrollToBottom: jest.fn() }),
  };
});

jest.mock("@/components/common/safari-scroll-fix", () => ({
  SafariScrollFix: ({ children }: { children?: React.ReactNode }) => (
    <>{children}</>
  ),
}));

jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-header",
  () => ({
    ChatHeader: () => <div data-testid="chat-header" />,
  }),
);

jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sidebar",
  () => ({
    ChatSidebar: () => <div data-testid="chat-sidebar" />,
  }),
);

jest.mock(
  "@/components/core/playgroundComponent/chat-view/hooks/use-send-message",
  () => ({
    useSendMessage: () => ({ sendMessage: jest.fn() }),
  }),
);

jest.mock(
  "@/components/core/playgroundComponent/hooks/use-get-flow-id",
  () => ({
    useGetFlowId: () => "flow-1",
  }),
);

jest.mock("@/components/ui/animated-close", () => ({
  AnimatedConditional: ({ children }: { children?: React.ReactNode }) => (
    <>{children}</>
  ),
}));

const mockSetOpen = jest.fn();
jest.mock("@/components/ui/simple-sidebar", () => ({
  useSimpleSidebar: () => ({
    open: true,
    setOpen: mockSetOpen,
    setWidth: jest.fn(),
  }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      inputs: [],
      nodes: [],
      isBuilding: false,
    }),
}));

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({ setChatValueStore: jest.fn() }),
}));

jest.mock("../../../chat-view/chat-input", () => ({
  ChatInput: () => <textarea data-testid="input-chat-playground" />,
}));

jest.mock("../../../chat-view/chat-input/hooks/use-drag-and-drop", () => ({
  __esModule: true,
  default: () => ({
    dragOver: jest.fn(),
    dragEnter: jest.fn(),
    dragLeave: jest.fn(),
  }),
}));

jest.mock("../../../chat-view/chat-messages", () => ({
  Messages: () => <div data-testid="messages" />,
}));

jest.mock("../../../chat-view/chat-messages/hooks/use-chat-history", () => ({
  useChatHistory: () => ({ chatHistory: [] }),
}));

jest.mock("../../../hooks/use-session-manager", () => ({
  useSessionManager: () => ({
    activeSessionId: "session-1",
    sessions: ["session-1"],
    createSession: jest.fn(),
    deleteSession: jest.fn(),
    bulkDeleteSessions: jest.fn(),
    renameSession: jest.fn(),
    selectSession: jest.fn(),
    clearDefaultSession: jest.fn(),
  }),
}));

const noop = () => {};

const renderPanel = () =>
  render(
    <FlowPageSlidingContainerContent isFullscreen setIsFullscreen={noop} />,
  );

describe("FlowPageSlidingContainerContent — Escape handling (WCAG 2.1.2)", () => {
  afterEach(() => {
    mockSetOpen.mockClear();
    document
      .querySelectorAll("[data-testid='fake-overlay']")
      .forEach((el) => el.remove());
  });

  it("closes the panel on Escape when nothing nested is open", () => {
    renderPanel();

    // Dispatch on a real element inside the panel (not `document` itself)
    // so `event.target` reflects where a real keypress would originate —
    // matching the panelRef-containment check the handler relies on.
    fireEvent.keyDown(screen.getByTestId("chat-header"), { key: "Escape" });

    expect(mockSetOpen).toHaveBeenCalledWith(false);
  });

  // Regression guard: this raw document-level listener used to close the
  // whole Playground panel on ANY Escape press, including ones meant for a
  // nested overlay (the Session logs modal, or the session row's "More
  // options" dropdown). Those overlays keep DOM focus on their own trigger
  // — which sits inside this panel — for as long as they're open, so
  // checking event.target's position alone can't tell "a dropdown is open,
  // let it self-close" apart from "nothing nested is open, close the
  // panel." The fix also checks for the overlay's own presence in the DOM.
  it("does not close the panel on Escape when a nested dialog is present, even if the keypress bubbles from inside the panel", () => {
    renderPanel();

    const overlay = document.createElement("div");
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("data-testid", "fake-overlay");
    document.body.appendChild(overlay);

    // Some overlays (e.g. the "More options" dropdown) keep DOM focus on
    // their trigger — which sits inside the panel — while open, so this
    // must be blocked purely by the overlay's presence, not by target
    // position. Dispatch from inside the panel to prove that.
    fireEvent.keyDown(screen.getByTestId("chat-header"), { key: "Escape" });

    expect(mockSetOpen).not.toHaveBeenCalled();
  });

  it("does not close the panel on Escape when a nested listbox is present", () => {
    renderPanel();

    const overlay = document.createElement("div");
    overlay.setAttribute("role", "listbox");
    overlay.setAttribute("data-testid", "fake-overlay");
    document.body.appendChild(overlay);

    fireEvent.keyDown(overlay, { key: "Escape" });

    expect(mockSetOpen).not.toHaveBeenCalled();
  });

  it("still closes the panel on Escape from inside it, once a nested overlay has been removed", () => {
    renderPanel();

    const overlay = document.createElement("div");
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("data-testid", "fake-overlay");
    document.body.appendChild(overlay);
    overlay.remove();

    fireEvent.keyDown(screen.getByTestId("chat-header"), { key: "Escape" });

    expect(mockSetOpen).toHaveBeenCalledWith(false);
  });

  it("ignores non-Escape keys", () => {
    renderPanel();

    fireEvent.keyDown(screen.getByTestId("chat-header"), { key: "a" });

    expect(mockSetOpen).not.toHaveBeenCalled();
  });
});
