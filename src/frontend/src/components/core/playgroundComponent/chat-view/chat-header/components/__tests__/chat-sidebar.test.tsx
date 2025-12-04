import { fireEvent, render, screen } from "@testing-library/react";
import { ChatSidebar } from "../chat-sidebar";

// Mock dependencies
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <div data-testid={`icon-${name}`} className={className}>
      {name}
    </div>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content: string;
  }) => <div data-testid={`tooltip-${content}`}>{children}</div>,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
  } & Record<string, unknown>) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

const mockUseGetFlowId = jest.fn().mockReturnValue("flow-123");
jest.mock("../../../hooks/use-get-flow-id", () => ({
  useGetFlowId: () => mockUseGetFlowId(),
}));

const mockUseGetSessionsFromFlowQuery = jest.fn();
jest.mock(
  "@/controllers/API/queries/messages/use-get-sessions-from-flow",
  () => ({
    useGetSessionsFromFlowQuery: (params: { id: string }) =>
      mockUseGetSessionsFromFlowQuery(params),
  }),
);

jest.mock("../session-selector", () => ({
  SessionSelector: ({
    session,
    isVisible,
    toggleVisibility,
    deleteSession,
  }: {
    session: string;
    isVisible: boolean;
    toggleVisibility: () => void;
    deleteSession: (session: string) => void;
  }) => (
    <div
      data-testid={`session-${session}`}
      data-visible={isVisible}
      onClick={toggleVisibility}
    >
      <span>{session}</span>
      <button
        data-testid={`delete-${session}`}
        onClick={(e) => {
          e.stopPropagation();
          deleteSession(session);
        }}
      >
        Delete
      </button>
    </div>
  ),
}));

describe("ChatSidebar", () => {
  const defaultProps = {
    onNewChat: jest.fn(),
    onSessionSelect: jest.fn(),
    currentSessionId: "session-1",
    onDeleteSession: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseGetFlowId.mockReturnValue("flow-123");
    mockUseGetSessionsFromFlowQuery.mockReturnValue({
      data: { sessions: ["session-1", "session-2"] },
      isLoading: false,
    });
  });

  it("renders New Chat button with Plus icon", () => {
    render(<ChatSidebar {...defaultProps} />);
    expect(screen.getByTestId("new-chat")).toBeInTheDocument();
    expect(screen.getByTestId("icon-Plus")).toBeInTheDocument();
    expect(screen.getByTestId("tooltip-New Chat")).toBeInTheDocument();
  });

  it("shows loading state when fetching sessions", () => {
    mockUseGetSessionsFromFlowQuery.mockReturnValue({
      data: null,
      isLoading: true,
    });
    render(<ChatSidebar {...defaultProps} />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders sessions list when data is loaded", () => {
    render(<ChatSidebar {...defaultProps} />);
    expect(screen.getByTestId("session-session-1")).toBeInTheDocument();
    expect(screen.getByTestId("session-session-2")).toBeInTheDocument();
  });

  it("ensures currentFlowId is always in the sessions list", () => {
    mockUseGetSessionsFromFlowQuery.mockReturnValue({
      data: { sessions: ["session-1"] },
      isLoading: false,
    });
    render(<ChatSidebar {...defaultProps} />);
    // flow-123 should be added as default session
    expect(screen.getByTestId("session-flow-123")).toBeInTheDocument();
  });

  it("ensures currentSessionId is in the list even if not in API response", () => {
    mockUseGetSessionsFromFlowQuery.mockReturnValue({
      data: { sessions: [] },
      isLoading: false,
    });
    render(<ChatSidebar {...defaultProps} currentSessionId="new-session" />);
    expect(screen.getByTestId("session-new-session")).toBeInTheDocument();
  });

  it("calls onNewChat when New Chat button is clicked", () => {
    const onNewChat = jest.fn();
    render(<ChatSidebar {...defaultProps} onNewChat={onNewChat} />);
    fireEvent.click(screen.getByTestId("new-chat"));
    expect(onNewChat).toHaveBeenCalledTimes(1);
  });

  it("calls onSessionSelect when a session is clicked", () => {
    const onSessionSelect = jest.fn();
    render(<ChatSidebar {...defaultProps} onSessionSelect={onSessionSelect} />);
    fireEvent.click(screen.getByTestId("session-session-2"));
    expect(onSessionSelect).toHaveBeenCalledWith("session-2");
  });

  it("marks current session as visible", () => {
    render(<ChatSidebar {...defaultProps} currentSessionId="session-1" />);
    expect(screen.getByTestId("session-session-1")).toHaveAttribute(
      "data-visible",
      "true",
    );
    expect(screen.getByTestId("session-session-2")).toHaveAttribute(
      "data-visible",
      "false",
    );
  });

  it("calls onDeleteSession when delete button is clicked", () => {
    const onDeleteSession = jest.fn();
    render(<ChatSidebar {...defaultProps} onDeleteSession={onDeleteSession} />);
    fireEvent.click(screen.getByTestId("delete-session-2"));
    expect(onDeleteSession).toHaveBeenCalledWith("session-2");
  });

  it("switches to default session when deleting current session", () => {
    const onDeleteSession = jest.fn();
    const onSessionSelect = jest.fn();
    render(
      <ChatSidebar
        {...defaultProps}
        currentSessionId="session-1"
        onDeleteSession={onDeleteSession}
        onSessionSelect={onSessionSelect}
      />,
    );
    fireEvent.click(screen.getByTestId("delete-session-1"));
    expect(onDeleteSession).toHaveBeenCalledWith("session-1");
    expect(onSessionSelect).toHaveBeenCalledWith("flow-123");
  });

  it("handles empty sessions list gracefully", () => {
    mockUseGetSessionsFromFlowQuery.mockReturnValue({
      data: { sessions: [] },
      isLoading: false,
    });
    render(<ChatSidebar {...defaultProps} currentSessionId={undefined} />);
    // Should still show the default session (flow-123)
    expect(screen.getByTestId("session-flow-123")).toBeInTheDocument();
  });
});
