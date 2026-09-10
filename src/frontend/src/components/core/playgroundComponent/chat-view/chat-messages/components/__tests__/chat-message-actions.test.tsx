import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
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

jest.mock("../error-message", () => ({
  __esModule: true,
  ErrorView: () => <div data-testid="error-view" />,
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: () => ({
    isBuilding: false,
    fitViewNode: jest.fn(),
  }),
}));

jest.mock("../../hooks/use-thinking-duration", () => ({
  useThinkingDurationStore: Object.assign(() => ({ startTime: Date.now() }), {
    getState: () => ({ startTime: Date.now() }),
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
  default: ({ name }: { name?: string }) => (
    <div data-testid={name ? `icon-${name}` : "icon"} />
  ),
  ForwardedIconComponent: () => <div data-testid="forwarded-icon" />,
}));

jest.mock("@/components/common/sanitizedHTMLWrapper", () => ({
  __esModule: true,
  default: () => <div data-testid="sanitized-html" />,
}));

jest.mock("@/components/core/chatComponents/ContentBlockDisplay", () => ({
  ContentBlockDisplay: () => <div data-testid="content-block" />,
}));

jest.mock("../edit-message-field", () => ({
  __esModule: true,
  default: () => <div data-testid="edit-message-field" />,
}));

jest.mock("../file-card-wrapper", () => ({
  __esModule: true,
  default: () => <div data-testid="file-card-wrapper" />,
}));

// Deliberately NOT mocking ../message-options here (unlike chat-message.test.tsx)
// — this file exists specifically to exercise the real EditMessageButton, so
// axe and real .focus()/toHaveFocus() assertions mean something.

jest.mock("@/customization/components/custom-markdown-field", () => ({
  CustomMarkdownField: ({ chatMessage }: { chatMessage: string }) => (
    <div data-testid="markdown-field">{chatMessage}</div>
  ),
}));

jest.mock("@/customization/components/custom-profile-icon", () => ({
  CustomProfileIcon: () => <div data-testid="profile-icon" />,
}));

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: () => ({
    awaitingBotResponse: false,
    setAwaitingBotResponse: jest.fn(),
  }),
}));

jest.mock("../../hooks/use-typing-effect", () => ({
  useTypingEffect: ({ text }: { text: string }) => ({
    displayedText: text,
    isTyping: false,
  }),
}));

describe("ChatMessage actions (playgroundComponent) — WCAG 2.1.1 keyboard reachability", () => {
  const mockChat = {
    id: "1",
    message: "Hello World",
    isSend: false,
    sender_name: "AI",
    timestamp: "2024-01-01T10:00:00Z",
    session: "session-1",
    files: [],
    properties: {},
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

  it("has no detectable axe violations", async () => {
    const { container } = render(<ChatMessage {...defaultProps} />);

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  // Regression guard: the copy/edit/feedback actions used to be hidden with
  // `invisible` + `group-hover:visible`, which removes them from the tab
  // order entirely (visibility:hidden elements can't receive focus). The
  // sibling chat-message.test.tsx mocks EditMessageButton away entirely, so
  // it can't catch this — this file renders the real component.
  it("keeps message action buttons focusable, not just hover-revealed", () => {
    render(<ChatMessage {...defaultProps} />);

    const copyButton = screen.getByRole("button", { name: "Copy message" });
    const helpfulButton = screen.getByTestId("helpful-button");
    const notHelpfulButton = screen.getByTestId("not-helpful-button");

    for (const button of [copyButton, helpfulButton, notHelpfulButton]) {
      expect(button).not.toHaveAttribute("tabIndex", "-1");
      expect(button).not.toBeDisabled();
      button.focus();
      expect(button).toHaveFocus();
    }

    const actionsWrapper = copyButton.closest(
      "[class*='absolute']",
    ) as HTMLElement;
    expect(actionsWrapper).not.toBeNull();
    expect(actionsWrapper.className).not.toContain("invisible");
    expect(actionsWrapper.className).toContain("opacity-0");
    expect(actionsWrapper.className).toContain(
      "group-focus-within:opacity-100",
    );
  });
});
