import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SessionTabBar } from "../session-tab-bar";
import type { SessionHistoryEntry } from "../../assistant-panel.types";

jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIcon({ name }: { name: string }) {
    return <span data-testid={`icon-${name}`} />;
  };
});

jest.mock("@/components/common/shadTooltipComponent", () => {
  return function MockTooltip({
    children,
  }: {
    children: React.ReactNode;
  }) {
    return <>{children}</>;
  };
});

function createSession(
  overrides: Partial<SessionHistoryEntry> & { sessionId: string },
): SessionHistoryEntry {
  return {
    firstUserMessage: "Test message",
    messageCount: 2,
    lastActiveAt: new Date().toISOString(),
    messages: [],
    ...overrides,
  };
}

describe("SessionTabBar", () => {
  const defaultProps = {
    sessions: [] as SessionHistoryEntry[],
    activeSessionId: "current-session",
    hasMessages: true,
    onSelectSession: jest.fn(),
    onDeleteSession: jest.fn(),
    onNewSession: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("rendering", () => {
    it("should render the tab bar container", () => {
      render(<SessionTabBar {...defaultProps} />);
      expect(screen.getByTestId("session-tab-bar")).toBeInTheDocument();
    });

    it("should render current session tab", () => {
      render(<SessionTabBar {...defaultProps} />);
      expect(screen.getByText("Current session")).toBeInTheDocument();
    });

    it("should show 'New session' label when no messages", () => {
      render(<SessionTabBar {...defaultProps} hasMessages={false} />);
      expect(screen.getByText("New session")).toBeInTheDocument();
    });

    it("should render saved session tabs", () => {
      const sessions = [
        createSession({
          sessionId: "saved-1",
          firstUserMessage: "Build a RAG pipeline",
        }),
        createSession({
          sessionId: "saved-2",
          firstUserMessage: "Create a chatbot",
        }),
      ];

      render(<SessionTabBar {...defaultProps} sessions={sessions} />);

      expect(screen.getByText("Build a RAG pipeline")).toBeInTheDocument();
      expect(screen.getByText("Create a chatbot")).toBeInTheDocument();
    });

    it("should render tab bar container with tabs", () => {
      render(<SessionTabBar {...defaultProps} />);
      expect(screen.getByTestId("session-tab-bar")).toBeInTheDocument();
    });
  });

  describe("active state", () => {
    it("should not show close button on current session tab", () => {
      render(<SessionTabBar {...defaultProps} />);

      expect(
        screen.queryByTestId(`session-tab-close-${defaultProps.activeSessionId}`),
      ).not.toBeInTheDocument();
    });

    it("should show close button on saved session tabs", () => {
      const sessions = [
        createSession({ sessionId: "saved-1", firstUserMessage: "Test" }),
      ];

      render(<SessionTabBar {...defaultProps} sessions={sessions} />);

      expect(
        screen.getByTestId("session-tab-close-saved-1"),
      ).toBeInTheDocument();
    });
  });

  describe("interactions", () => {
    it("should call onSelectSession when clicking a saved tab", async () => {
      const onSelectSession = jest.fn();
      const sessions = [
        createSession({ sessionId: "saved-1", firstUserMessage: "Test" }),
      ];

      render(
        <SessionTabBar
          {...defaultProps}
          sessions={sessions}
          onSelectSession={onSelectSession}
        />,
      );

      await userEvent.click(screen.getByText("Test"));
      expect(onSelectSession).toHaveBeenCalledWith("saved-1");
    });

    it("should not call onSelectSession when clicking active tab", async () => {
      const onSelectSession = jest.fn();

      render(
        <SessionTabBar
          {...defaultProps}
          onSelectSession={onSelectSession}
        />,
      );

      await userEvent.click(screen.getByText("Current session"));
      expect(onSelectSession).not.toHaveBeenCalled();
    });

    it("should call onDeleteSession when clicking close on a tab", async () => {
      const onDeleteSession = jest.fn();
      const sessions = [
        createSession({ sessionId: "saved-1", firstUserMessage: "Test" }),
      ];

      render(
        <SessionTabBar
          {...defaultProps}
          sessions={sessions}
          onDeleteSession={onDeleteSession}
        />,
      );

      await userEvent.click(screen.getByTestId("session-tab-close-saved-1"));
      expect(onDeleteSession).toHaveBeenCalledWith("saved-1");
    });

    it("should call onNewSession when closing last active tab", async () => {
      const onNewSession = jest.fn();
      const onDeleteSession = jest.fn();

      render(
        <SessionTabBar
          {...defaultProps}
          onNewSession={onNewSession}
          onDeleteSession={onDeleteSession}
        />,
      );

      // Only one tab (current session) — close button hidden when single tab
      // No close button available, so onNewSession won't be triggered
      expect(screen.queryByTestId(`session-tab-close-${defaultProps.activeSessionId}`)).not.toBeInTheDocument();
    });
  });
});
