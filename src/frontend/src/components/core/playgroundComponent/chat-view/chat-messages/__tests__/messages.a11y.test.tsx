import { render, screen } from "@testing-library/react";
import { Messages } from "../messages";

// The completion cue and live-region semantics are what is under test; the
// message list itself, scrolling, and stores are stubbed to isolate them.
jest.mock("use-stick-to-bottom", () => {
  const StickToBottom = ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  );
  StickToBottom.Content = ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  );
  return {
    StickToBottom,
    useStickToBottomContext: () => ({ scrollRef: { current: null } }),
  };
});

jest.mock("@/components/common/safari-scroll-fix", () => ({
  SafariScrollFix: () => null,
}));

jest.mock("../components/chat-message", () => ({
  __esModule: true,
  default: ({ chat }: { chat: { id: string } }) => (
    <div data-testid={`chat-message-${chat.id}`} />
  ),
}));

jest.mock("../components/bot-message", () => ({
  BotMessage: () => <div data-testid="bot-placeholder" />,
}));

const mockChatHistory: { chatHistory: object[] } = { chatHistory: [] };
jest.mock("../hooks/use-chat-history", () => ({
  useChatHistory: () => ({
    chatHistory: mockChatHistory.chatHistory,
    loadMore: jest.fn(),
    hasMore: false,
    isLoadingMore: false,
  }),
}));

const mockFlowState = { isBuilding: false, outputs: [] as { type: string }[] };
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof mockFlowState) => unknown) =>
    selector(mockFlowState),
}));

jest.mock("@/stores/playgroundStore", () => ({
  usePlaygroundStore: (selector: (state: { isOpen: boolean }) => unknown) =>
    selector({ isOpen: false }),
}));

const userMessage = { id: "u1", message: "hi", isSend: true };
const botMessage = { id: "b1", message: "hello back", isSend: false };

describe("Messages live region accessibility", () => {
  beforeEach(() => {
    mockFlowState.isBuilding = false;
    mockFlowState.outputs = [];
    mockChatHistory.chatHistory = [];
  });

  it("should_expose_the_message_list_as_a_named_muted_log_region", () => {
    mockChatHistory.chatHistory = [userMessage, botMessage];

    render(<Messages visibleSession={null} />);

    // The list must NOT be live: React remounts earlier messages on send,
    // which a live region re-announces as additions (Safari/VoiceOver read
    // the whole history on every send — LE-2041 QA). aria-live="off"
    // overrides role="log"'s implicit politeness; announcements come from
    // the separate status region only.
    const log = screen.getByRole("log", { name: "Chat messages" });
    expect(log).toHaveAttribute("aria-live", "off");
    expect(log).not.toHaveAttribute("aria-relevant");
    expect(log).not.toHaveAttribute("aria-busy");
  });

  it("should_announce_the_reply_content_once_the_build_settles", () => {
    mockFlowState.isBuilding = true;
    mockChatHistory.chatHistory = [userMessage, botMessage];

    const { rerender } = render(<Messages visibleSession={null} />);
    expect(screen.getByRole("status")).toBeEmptyDOMElement();

    mockFlowState.isBuilding = false;
    rerender(<Messages visibleSession={null} />);

    // The transcript is muted, so this status region is the reply's only
    // path to the screen reader — it must carry the reply text itself, not
    // just a "done" cue (LE-2041 QA).
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("hello back");
  });

  it("should_not_announce_when_the_build_settles_without_a_bot_reply", () => {
    mockFlowState.isBuilding = true;
    mockChatHistory.chatHistory = [userMessage];

    const { rerender } = render(<Messages visibleSession={null} />);

    mockFlowState.isBuilding = false;
    rerender(<Messages visibleSession={null} />);

    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("should_not_announce_anything_on_initial_render", () => {
    mockChatHistory.chatHistory = [userMessage, botMessage];

    render(<Messages visibleSession={null} />);

    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });
});
