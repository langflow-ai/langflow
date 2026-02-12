import { render, screen } from "@testing-library/react";
import type { ChatMessageType } from "@/types/chat";
import { BotMessage } from "../bot-message";
import { UserMessage } from "../user-message";

jest.mock("@/assets/LangflowLogo.svg?react", () => ({
  __esModule: true,
  default: () => <div data-testid="langflow-logo" />,
}));

jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="markdown">{children}</div>
  ),
}));
jest.mock("remark-gfm", () => ({ __esModule: true, default: () => {} }));
jest.mock("rehype-mathjax", () => ({ __esModule: true, default: () => {} }));

let mockPlaygroundPage = false;

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) => {
    const state = {
      isBuilding: false,
      fitViewNode: jest.fn(),
      playgroundPage: mockPlaygroundPage,
      buildStartTime: null,
      buildDuration: null,
    };
    return typeof selector === "function" ? selector(state) : state;
  },
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) => {
    const state = { currentFlowId: "flow-id" };
    return typeof selector === "function" ? selector(state) : state;
  },
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) => {
    const state = { setErrorData: jest.fn(), setSuccessData: jest.fn() };
    return typeof selector === "function" ? selector(state) : state;
  },
}));

jest.mock("@/controllers/API/queries/messages", () => ({
  useUpdateMessage: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name?: string; className?: string }) => (
    <div data-testid={name ? `icon-${name}` : "icon"} className={className} />
  ),
  ForwardedIconComponent: ({
    name,
    className,
  }: {
    name?: string;
    className?: string;
  }) => (
    <div
      data-testid={name ? `icon-${name}` : "forwarded-icon"}
      className={className}
    />
  ),
}));

jest.mock("@/components/core/chatComponents/ContentBlockDisplay", () => ({
  ContentBlockDisplay: () => <div data-testid="content-block" />,
}));

jest.mock("../edit-message-field", () => ({
  __esModule: true,
  default: () => <div data-testid="edit-message-field" />,
}));

jest.mock("../message-options", () => ({
  EditMessageButton: ({
    onEdit,
    isBotMessage,
    onEvaluate,
  }: {
    onEdit?: () => void;
    isBotMessage?: boolean;
    onEvaluate?: (value: boolean | null) => void;
  }) => (
    <div data-testid="edit-message-button">
      {onEdit && <button data-testid="edit-action">Edit</button>}
      <button data-testid="copy-action">Copy</button>
      {isBotMessage && <button data-testid="thumbs-action">Thumbs</button>}
      {onEvaluate && <button data-testid="evaluate-action">Evaluate</button>}
    </div>
  ),
}));

jest.mock("@/customization/components/custom-markdown-field", () => ({
  CustomMarkdownField: ({ chatMessage }: { chatMessage: string }) => (
    <div data-testid="markdown-field">{chatMessage}</div>
  ),
}));

jest.mock("@/customization/components/custom-profile-icon", () => ({
  CustomProfileIcon: () => <div data-testid="profile-icon" />,
}));

const baseBotChat: ChatMessageType = {
  id: "bot-1",
  message: "Hello from bot",
  isSend: false,
  sender_name: "AI",
  timestamp: "2024-01-01T10:00:00Z",
  session: "session-1",
  files: [],
  category: "message",
};

const baseUserChat: ChatMessageType = {
  id: "user-1",
  message: "Hello from user",
  isSend: true,
  sender_name: "User",
  timestamp: "2024-01-01T10:00:00Z",
  session: "session-1",
  files: [],
  category: "message",
};

const renderBotMessage = () =>
  render(
    <BotMessage
      chat={baseBotChat}
      lastMessage={false}
      updateChat={jest.fn()}
      playgroundPage={true}
    />,
  );

const renderUserMessage = () =>
  render(
    <UserMessage
      chat={baseUserChat}
      lastMessage={false}
      updateChat={jest.fn()}
      playgroundPage={true}
    />,
  );

describe("BotMessage in shareable playground", () => {
  beforeEach(() => {
    mockPlaygroundPage = true;
  });

  it("should show copy button", () => {
    renderBotMessage();
    expect(screen.getByTestId("copy-action")).toBeInTheDocument();
  });

  it("should hide edit button", () => {
    renderBotMessage();
    expect(screen.queryByTestId("edit-action")).not.toBeInTheDocument();
  });

  it("should hide thumbs up/down", () => {
    renderBotMessage();
    expect(screen.queryByTestId("thumbs-action")).not.toBeInTheDocument();
  });
});

describe("BotMessage in normal playground", () => {
  beforeEach(() => {
    mockPlaygroundPage = false;
  });

  it("should show edit button", () => {
    renderBotMessage();
    expect(screen.getByTestId("edit-action")).toBeInTheDocument();
  });

  it("should show thumbs up/down", () => {
    renderBotMessage();
    expect(screen.getByTestId("thumbs-action")).toBeInTheDocument();
  });

  it("should show copy button", () => {
    renderBotMessage();
    expect(screen.getByTestId("copy-action")).toBeInTheDocument();
  });
});

describe("UserMessage in shareable playground", () => {
  beforeEach(() => {
    mockPlaygroundPage = true;
  });

  it("should show copy button", () => {
    renderUserMessage();
    expect(screen.getByTestId("copy-action")).toBeInTheDocument();
  });

  it("should hide edit button", () => {
    renderUserMessage();
    expect(screen.queryByTestId("edit-action")).not.toBeInTheDocument();
  });

  it("should hide evaluate action", () => {
    renderUserMessage();
    expect(screen.queryByTestId("evaluate-action")).not.toBeInTheDocument();
  });
});

describe("UserMessage in normal playground", () => {
  beforeEach(() => {
    mockPlaygroundPage = false;
  });

  it("should show edit button", () => {
    renderUserMessage();
    expect(screen.getByTestId("edit-action")).toBeInTheDocument();
  });

  it("should show copy button", () => {
    renderUserMessage();
    expect(screen.getByTestId("copy-action")).toBeInTheDocument();
  });

  it("should show evaluate action", () => {
    renderUserMessage();
    expect(screen.getByTestId("evaluate-action")).toBeInTheDocument();
  });
});
