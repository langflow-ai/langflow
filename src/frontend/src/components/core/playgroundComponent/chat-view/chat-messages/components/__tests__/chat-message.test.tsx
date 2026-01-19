import { render, screen } from "@testing-library/react";
import ChatMessage from "../chat-message";
import ThinkingMessage from "../thinking-message";

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

// Mock error-message to avoid ES module issues
jest.mock("../error-message", () => ({
  __esModule: true,
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

// Mock the thinking duration store
jest.mock("../../hooks/use-thinking-duration", () => ({
  useThinkingDurationStore: Object.assign(
    () => ({
      startTime: Date.now(),
    }),
    {
      getState: () => ({
        startTime: Date.now(),
      }),
    },
  ),
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
  default: ({ name, className }: { name?: string; className?: string }) => (
    <div data-testid={name ? `icon-${name}` : "icon"} className={className} />
  ),
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

describe("ThinkingMessage Component", () => {
  it("renders thinking state correctly", () => {
    render(<ThinkingMessage isThinking={true} duration={null} />);

    expect(screen.getByTestId("icon-Brain")).toBeInTheDocument();
    expect(screen.getByText(/Thinking for/)).toBeInTheDocument();
  });

  it("renders thought state with duration", () => {
    render(<ThinkingMessage isThinking={false} duration={5000} />);

    expect(screen.getByTestId("icon-Brain")).toBeInTheDocument();
    expect(screen.getByText(/Thought for/)).toBeInTheDocument();
    expect(screen.getByText(/5.0s/)).toBeInTheDocument();
  });

  it("applies pulse animation when thinking", () => {
    render(<ThinkingMessage isThinking={true} duration={null} />);

    const icon = screen.getByTestId("icon-Brain");
    expect(icon.className).toContain("animate-pulse");
    expect(icon.className).toContain("text-primary");
  });

  it("applies muted color when not thinking", () => {
    render(<ThinkingMessage isThinking={false} duration={3000} />);

    const icon = screen.getByTestId("icon-Brain");
    expect(icon.className).toContain("text-muted-foreground");
    expect(icon.className).not.toContain("animate-pulse");
  });

  it("formats time in minutes when duration exceeds 60 seconds", () => {
    render(<ThinkingMessage isThinking={false} duration={90000} />);

    expect(screen.getByText(/1m 30s/)).toBeInTheDocument();
  });

  it("shows 0s when duration is null and not thinking", () => {
    render(<ThinkingMessage isThinking={false} duration={null} />);

    expect(screen.getByText(/Thought for/)).toBeInTheDocument();
    expect(screen.getByText(/0.0s/)).toBeInTheDocument();
  });
});
