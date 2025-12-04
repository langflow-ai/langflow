import { render, screen } from "@testing-library/react";
import ChatMessage from "../chat-message";

// Mock SVG imports
jest.mock("@/assets/LangflowLogo.svg?react", () => ({
  __esModule: true,
  default: () => <div data-testid="langflow-logo" />,
}));

// Mock ES modules that Jest can't handle
jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="markdown">{children}</div>
  ),
}));
jest.mock("remark-gfm", () => ({ __esModule: true, default: () => {} }));
jest.mock("rehype-mathjax", () => ({ __esModule: true, default: () => {} }));

// Mock content-view to avoid ES module issues
jest.mock("../content-view", () => ({
  ErrorView: ({ blocks }: { blocks: unknown[] }) => (
    <div data-testid="error-view">Error: {blocks?.length || 0} blocks</div>
  ),
}));

// Mock dependencies
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: () => ({
    isBuilding: false,
    fitViewNode: jest.fn(),
  }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: () => "flow-id",
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

jest.mock("@/controllers/API/queries/messages", () => ({
  useUpdateMessage: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="icon" />,
  ForwardedIconComponent: () => <div data-testid="forwarded-icon" />,
}));

jest.mock("@/components/common/sanitizedHTMLWrapper", () => ({
  __esModule: true,
  default: ({ content }) => <div data-testid="sanitized-html">{content}</div>,
}));

jest.mock("@/components/core/chatComponents/ContentBlockDisplay", () => ({
  ContentBlockDisplay: () => <div data-testid="content-block" />,
}));

// Mock child components
jest.mock("../edit-message-field", () => ({
  __esModule: true,
  default: () => <div data-testid="edit-message-field" />,
}));

jest.mock("../file-card-wrapper", () => ({
  __esModule: true,
  default: () => <div data-testid="file-card-wrapper" />,
}));

jest.mock("../message-options", () => ({
  EditMessageButton: () => <div data-testid="edit-message-button" />,
}));

jest.mock("@/customization/components/custom-markdown-field", () => ({
  CustomMarkdownField: ({ chatMessage }) => (
    <div data-testid="markdown-field">{chatMessage}</div>
  ),
}));

jest.mock("@/customization/components/custom-profile-icon", () => ({
  CustomProfileIcon: () => <div data-testid="profile-icon" />,
}));

// Mock stores used by BotMessage
jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: () => ({
    awaitingBotResponse: false,
    setAwaitingBotResponse: jest.fn(),
  }),
}));

// Mock hooks used by BotMessage
jest.mock("../../hooks/use-typing-effect", () => ({
  useTypingEffect: ({ text }: { text: string }) => ({
    displayedText: text,
    isTyping: false,
  }),
}));

describe("ChatMessage Component", () => {
  const mockChat = {
    id: "1",
    message: "Hello World",
    isSend: true,
    sender_name: "User",
    timestamp: "2024-01-01T10:00:00Z",
    session: "session-1",
    files: [],
    properties: {
      source: {
        id: "test-source",
        display_name: "Test Source",
        source: "test",
      },
    },
    content_blocks: [],
    category: "message",
  };

  const defaultProps = {
    chat: mockChat,
    lastMessage: false,
    updateChat: jest.fn(),
    closeChat: jest.fn(),
    playgroundPage: true,
  };

  it("renders user message correctly", () => {
    render(<ChatMessage {...defaultProps} />);
    expect(screen.getByText("Hello World")).toBeInTheDocument();
    expect(
      screen.getByTestId("chat-message-User-Hello World"),
    ).toBeInTheDocument();
  });

  it("renders bot message correctly", () => {
    const botProps = {
      ...defaultProps,
      chat: {
        ...mockChat,
        isSend: false,
        sender_name: "AI",
      },
    };

    render(<ChatMessage {...botProps} />);
    expect(screen.getByText("Hello World")).toBeInTheDocument();
    expect(
      screen.getByTestId("chat-message-AI-Hello World"),
    ).toBeInTheDocument();
  });

  it("renders user message with files even when text is empty", () => {
    const propsWithFiles = {
      ...defaultProps,
      chat: {
        ...mockChat,
        message: "",
        files: ["/path/to/file.jpg"],
      },
    };

    render(<ChatMessage {...propsWithFiles} />);
    // Should render UserMessage (with file-card-wrapper) not BotMessage
    expect(screen.getByTestId("file-card-wrapper")).toBeInTheDocument();
  });

  it("renders bot message when no text and no files", () => {
    const emptyProps = {
      ...defaultProps,
      chat: {
        ...mockChat,
        message: "",
        files: [],
      },
    };

    render(<ChatMessage {...emptyProps} />);
    // Empty user message with no files should render as BotMessage
    expect(screen.getByTestId("langflow-logo")).toBeInTheDocument();
  });
});
