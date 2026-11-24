import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import ChatMessage from "../chat-message";

jest.mock("../../../../../../assets/robot.png", () => "robot.png");

jest.mock("@/components/common/messageMetadataComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="message-metadata" />,
}));

jest.mock("@/components/core/chatComponents/ContentBlockDisplay", () => ({
  ContentBlockDisplay: () => <div data-testid="content-block-display" />,
}));

jest.mock("@/controllers/API/queries/messages", () => ({
  useUpdateMessage: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/customization/components/custom-markdown-field", () => ({
  CustomMarkdownField: ({ chatMessage }: { chatMessage: string }) => (
    <div data-testid="markdown-field">{chatMessage}</div>
  ),
}));

jest.mock("@/customization/components/custom-profile-icon", () => ({
  CustomProfileIcon: () => <div data-testid="profile-icon" />,
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: () => "flow-id",
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => jest.fn(),
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

jest.mock("../components/content-view", () => ({
  ErrorView: () => <div data-testid="error-view" />,
}));

jest.mock("../components/edit-message-field", () => ({
  __esModule: true,
  default: () => <div data-testid="edit-message-field" />,
}));

jest.mock("../components/file-card-wrapper", () => ({
  __esModule: true,
  default: () => <div data-testid="file-card-wrapper" />,
}));

describe("ChatMessage actions (WCAG 2.1.1 keyboard reachability)", () => {
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
    playgroundPage: false,
  };

  it("has no detectable axe violations", async () => {
    const { container } = render(<ChatMessage {...defaultProps} />);

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  // Regression guard: the copy/edit/feedback actions used to be hidden with
  // `invisible` + `group-hover:visible`, which removes them from the tab
  // order entirely (visibility:hidden elements can't receive focus) — a
  // keyboard-only user could never Tab to them. The fix keeps them in the
  // tab order via opacity + pointer-events instead, and reveals them on
  // `group-focus-within` as well as `group-hover`.
  it("keeps message action buttons focusable and reveals them on focus, not just hover", () => {
    render(<ChatMessage {...defaultProps} />);

    const copyButton = screen.getByRole("button", {
      name: "Copy message",
    });
    const editButton = screen.getByRole("button", {
      name: "Edit message",
    });
    const helpfulButton = screen.getByTestId("helpful-button");
    const notHelpfulButton = screen.getByTestId("not-helpful-button");

    for (const button of [
      copyButton,
      editButton,
      helpfulButton,
      notHelpfulButton,
    ]) {
      expect(button).not.toHaveAttribute("tabIndex", "-1");
      expect(button).not.toBeDisabled();
      button.focus();
      expect(button).toHaveFocus();
    }

    // Walk up to the positioned wrapper that toggles visibility.
    const actionsWrapper = copyButton.closest(
      "[class*='absolute']",
    ) as HTMLElement;
    expect(actionsWrapper).not.toBeNull();
    expect(actionsWrapper.className).not.toMatch(/(?<!in)\bvisible\b/);
    expect(actionsWrapper.className).not.toContain("invisible");
    expect(actionsWrapper.className).toContain("opacity-0");
    expect(actionsWrapper.className).toContain(
      "group-focus-within:opacity-100",
    );
  });
});
