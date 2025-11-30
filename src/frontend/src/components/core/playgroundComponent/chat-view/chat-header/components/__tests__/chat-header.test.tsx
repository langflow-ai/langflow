import { render, screen } from "@testing-library/react";
import { ChatHeader } from "../chat-header";

// Mock dependencies
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <div data-testid={`icon-${name}`} className={className} />
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

jest.mock("@/components/ui/select-custom", () => ({
  Select: ({
    children,
    value,
    onValueChange,
  }: {
    children: React.ReactNode;
    value: string;
    onValueChange?: (value: string) => void;
  }) => (
    <div data-testid="select" data-value={value}>
      {children}
    </div>
  ),
  SelectTrigger: ({
    children,
    onClick,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: (e: React.MouseEvent) => void;
  } & Record<string, unknown>) => (
    <button data-testid="select-trigger" onClick={onClick} {...props}>
      {children}
    </button>
  ),
  SelectContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="select-content">{children}</div>
  ),
  SelectItem: ({
    children,
    value,
    onClick,
  }: {
    children: React.ReactNode;
    value: string;
    onClick?: () => void;
  }) => (
    <div data-testid={`select-item-${value}`} onClick={() => onClick?.()}>
      {children}
    </div>
  ),
}));

jest.mock("@/controllers/API/queries/messages/use-rename-session", () => ({
  useUpdateSessionName: () => ({
    mutate: jest.fn(),
  }),
}));

jest.mock("../chat-sessions-dropdown", () => ({
  ChatSessionsDropdown: ({
    onNewChat,
    onSessionSelect,
    currentSessionId,
  }: {
    onNewChat?: () => void;
    onSessionSelect?: (sessionId: string) => void;
    currentSessionId?: string;
  }) => (
    <div
      data-testid="chat-sessions-dropdown"
      data-current-session={currentSessionId}
    >
      <button data-testid="dropdown-new-chat" onClick={onNewChat}>
        New Chat
      </button>
      <button
        data-testid="dropdown-select-session"
        onClick={() => onSessionSelect?.("session-1")}
      >
        Select Session
      </button>
    </div>
  ),
}));

jest.mock("../session-logs-modal", () => ({
  SessionLogsModal: ({
    open,
    sessionId,
  }: {
    open: boolean;
    sessionId: string;
  }) =>
    open ? (
      <div data-testid="session-logs-modal" data-session-id={sessionId} />
    ) : null,
}));

jest.mock("../session-rename", () => ({
  SessionRename: ({
    sessionId,
    onSave,
  }: {
    sessionId?: string;
    onSave?: (value: string) => void;
  }) => (
    <div data-testid="session-rename">
      <input
        data-testid="rename-input"
        defaultValue={sessionId}
        onBlur={(e) => onSave?.(e.target.value)}
      />
    </div>
  ),
}));

describe("ChatHeader", () => {
  const defaultProps = {
    currentSessionId: "session-1",
    currentFlowId: "flow-1",
    onNewChat: jest.fn(),
    onSessionSelect: jest.fn(),
    onToggleFullscreen: jest.fn(),
    onDeleteSession: jest.fn(),
    onClose: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the component", () => {
    render(<ChatHeader {...defaultProps} />);
    expect(screen.getByText("session-1")).toBeInTheDocument();
  });

  it("displays 'Chat' when no session is selected", () => {
    render(<ChatHeader {...defaultProps} currentSessionId={undefined} />);
    expect(screen.getByText("Chat")).toBeInTheDocument();
  });

  it("displays 'Default Session' when currentSessionId equals currentFlowId", () => {
    render(
      <ChatHeader
        {...defaultProps}
        currentSessionId="flow-1"
        currentFlowId="flow-1"
      />,
    );
    expect(screen.getByText("Default Session")).toBeInTheDocument();
  });

  it("displays the session ID as title when it's not the default session", () => {
    render(<ChatHeader {...defaultProps} />);
    expect(screen.getByText("session-1")).toBeInTheDocument();
  });

  it("shows sessions dropdown when not in fullscreen", () => {
    render(<ChatHeader {...defaultProps} isFullscreen={false} />);
    expect(screen.getByTestId("chat-sessions-dropdown")).toBeInTheDocument();
  });

  it("shows fullscreen toggle button", () => {
    render(<ChatHeader {...defaultProps} />);
    const toggleButton = screen.getByLabelText("Enter fullscreen");
    expect(toggleButton).toBeInTheDocument();
  });

  it("shows exit fullscreen button when in fullscreen", () => {
    render(<ChatHeader {...defaultProps} isFullscreen={true} />);
    const toggleButton = screen.getByLabelText("Exit fullscreen");
    expect(toggleButton).toBeInTheDocument();
  });

  it("shows close button when in fullscreen", () => {
    render(<ChatHeader {...defaultProps} isFullscreen={true} />);
    const closeButton = screen.getByLabelText("Close and go back to flow");
    expect(closeButton).toBeInTheDocument();
  });

  it("calls onToggleFullscreen when toggle button is clicked", () => {
    const onToggleFullscreen = jest.fn();
    render(
      <ChatHeader {...defaultProps} onToggleFullscreen={onToggleFullscreen} />,
    );
    const toggleButton = screen.getByLabelText("Enter fullscreen");
    toggleButton.click();
    expect(onToggleFullscreen).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when close button is clicked in fullscreen", () => {
    const onClose = jest.fn();
    render(
      <ChatHeader {...defaultProps} isFullscreen={true} onClose={onClose} />,
    );
    const closeButton = screen.getByLabelText("Close and go back to flow");
    closeButton.click();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("applies custom className", () => {
    const { container } = render(
      <ChatHeader {...defaultProps} className="custom-class" />,
    );
    expect(container.firstChild).toHaveClass("custom-class");
  });
});
