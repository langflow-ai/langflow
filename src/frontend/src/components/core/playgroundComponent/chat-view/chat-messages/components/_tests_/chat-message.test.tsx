import { render, screen } from "@testing-library/react";
import type { ChatMessageType } from "@/types/chat";
import type { chatMessagePropsType } from "@/types/components";
import ChatMessage from "../chat-message";

// Mock dependencies
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (
    selector: (state: {
      isBuilding: boolean;
      fitViewNode: jest.Mock;
    }) => unknown,
  ) =>
    selector({
      isBuilding: false,
      fitViewNode: jest.fn(),
    }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { currentFlowId: string }) => unknown) =>
    selector({
      currentFlowId: "flow-id",
    }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: { setErrorData: jest.Mock }) => unknown) =>
    selector({
      setErrorData: jest.fn(),
    }),
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

describe("ChatMessage Component", () => {
  const mockChat: ChatMessageType = {
    id: "1",
    flow_id: "flow-1",
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

  const defaultProps: chatMessagePropsType = {
    chat: mockChat,
    lastMessage: false,
    updateChat: jest.fn(),
    closeChat: jest.fn(),
    playgroundPage: true,
  };

  it("renders user message correctly", () => {
    render(<ChatMessage {...defaultProps} />);

    expect(screen.getByText("User")).toBeInTheDocument();
    expect(screen.getByText("Hello World")).toBeInTheDocument();
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

    expect(screen.getByText("AI")).toBeInTheDocument();
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });
});
