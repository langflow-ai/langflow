import { act, render, screen } from "@testing-library/react";
import { ShareablePlaygroundContent } from "../shareable-playground-content";

// --- Mock SVG imports ---
jest.mock("@/assets/LangflowLogo.svg?react", () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => (
    <div data-testid="langflow-logo" title={props.title as string} />
  ),
}));

jest.mock("@/assets/LangflowLogoColor.svg?react", () => ({
  __esModule: true,
  default: () => <div data-testid="langflow-logo-color" />,
}));

// --- Mock UI components ---
jest.mock("@/components/ui/textAnimation", () => ({
  TextEffectPerChar: ({ children }: { children: React.ReactNode }) => (
    <span data-testid="text-effect">{children}</span>
  ),
}));

jest.mock("@/components/ui/animated-close", () => ({
  AnimatedConditional: ({
    children,
    isOpen,
  }: {
    children: React.ReactNode;
    isOpen: boolean;
  }) => (isOpen ? <div data-testid="animated-conditional">{children}</div> : null),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
  }) => (
    <button data-testid="button" onClick={onClick}>
      {children}
    </button>
  ),
}));

jest.mock("use-stick-to-bottom", () => {
  const Content = ({ children }: { children: React.ReactNode }) => (
    <div data-testid="stick-to-bottom-content">{children}</div>
  );

  const StickToBottom = ({ children }: { children: React.ReactNode }) => (
    <div data-testid="stick-to-bottom">{children}</div>
  );

  StickToBottom.Content = Content;

  return { StickToBottom };
});

jest.mock(
  "@/components/core/appHeaderComponent/components/ThemeButtons",
  () => ({
    __esModule: true,
    default: () => <div data-testid="theme-buttons" />,
  }),
);

// --- Mock hooks ---
const mockSendMessage = jest.fn();
const mockAddNewSession = jest.fn().mockReturnValue("new-session-id");
const mockRemoveLocalSession = jest.fn();
const mockRenameLocalSession = jest.fn();
const mockHandleDelete = jest.fn();
const mockSetChatValueStore = jest.fn();

jest.mock(
  "@/components/core/playgroundComponent/hooks/use-get-flow-id",
  () => ({
    useGetFlowId: () => "flow-123",
  }),
);

jest.mock(
  "@/components/core/playgroundComponent/chat-view/hooks/use-send-message",
  () => ({
    useSendMessage: () => ({ sendMessage: mockSendMessage }),
  }),
);

jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-header/hooks/use-get-add-sessions",
  () => ({
    useGetAddSessions: () => ({
      sessions: ["flow-123", "session-2"],
      addNewSession: mockAddNewSession,
      removeLocalSession: mockRemoveLocalSession,
      renameLocalSession: mockRenameLocalSession,
      fetchedSessions: [],
    }),
  }),
);

jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-header/hooks/use-edit-session-info",
  () => ({
    useEditSessionInfo: () => ({
      handleDelete: mockHandleDelete,
    }),
  }),
);

let mockChatHistory: unknown[] = [];
jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-messages/hooks/use-chat-history",
  () => ({
    useChatHistory: () => mockChatHistory,
  }),
);

jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-input/hooks/use-drag-and-drop",
  () => ({
    __esModule: true,
    default: () => ({
      dragOver: jest.fn(),
      dragEnter: jest.fn(),
      dragLeave: jest.fn(),
    }),
  }),
);

// --- Mock stores ---
let mockIsBuilding = false;
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      inputs: [],
      nodes: [],
      isBuilding: mockIsBuilding,
    }),
}));

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      setChatValueStore: mockSetChatValueStore,
    }),
}));

// --- Mock feature flags ---
let mockEnablePublish = true;
jest.mock("@/customization/feature-flags", () => ({
  get ENABLE_PUBLISH() {
    return mockEnablePublish;
  },
}));

// --- Mock utilities ---
jest.mock("@/customization/utils/analytics", () => ({
  track: jest.fn(),
}));

jest.mock("@/customization/utils/custom-open-new-tab", () => ({
  customOpenNewTab: jest.fn(),
}));

jest.mock("@/customization/utils/urls", () => ({
  LangflowButtonRedirectTarget: () => "https://langflow.org",
}));

// --- Mock child components (capture props for interaction testing) ---
let capturedSidebarProps: Record<string, unknown> = {};
jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-sidebar",
  () => ({
    ChatSidebar: (props: Record<string, unknown>) => {
      capturedSidebarProps = props;
      return <div data-testid="chat-sidebar" />;
    },
  }),
);

let capturedHeaderProps: Record<string, unknown> = {};
jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-header/components/chat-header",
  () => ({
    ChatHeader: (props: Record<string, unknown>) => {
      capturedHeaderProps = props;
      return <div data-testid="chat-header" />;
    },
  }),
);

jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-messages",
  () => ({
    Messages: () => <div data-testid="messages" />,
  }),
);

jest.mock(
  "@/components/core/playgroundComponent/chat-view/chat-input",
  () => ({
    ChatInput: () => <div data-testid="chat-input" />,
  }),
);

describe("ShareablePlaygroundContent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockChatHistory = [];
    mockIsBuilding = false;
    mockEnablePublish = true;
    capturedSidebarProps = {};
    capturedHeaderProps = {};
  });

  describe("Empty State", () => {
    it("should render empty state when no messages and not building", () => {
      // Arrange
      mockChatHistory = [];
      mockIsBuilding = false;

      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(screen.getByText("New chat")).toBeInTheDocument();
      expect(screen.getByTestId("new-chat-text")).toBeInTheDocument();
      expect(
        screen.getByText("Test your flow with a chat prompt"),
      ).toBeInTheDocument();
      expect(screen.getByTestId("langflow-logo")).toBeInTheDocument();
      expect(screen.queryByTestId("messages")).not.toBeInTheDocument();
    });

    it("should render Messages when chat history has items", () => {
      // Arrange
      mockChatHistory = [
        { id: "1", message: "Hello", isSend: true, sender_name: "User" },
      ];

      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(screen.getByTestId("messages")).toBeInTheDocument();
      expect(screen.queryByText("New chat")).not.toBeInTheDocument();
      expect(screen.queryByTestId("new-chat-text")).not.toBeInTheDocument();
    });

    it("should render Messages when building even with empty history", () => {
      // Arrange
      mockChatHistory = [];
      mockIsBuilding = true;

      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(screen.getByTestId("messages")).toBeInTheDocument();
      expect(screen.queryByText("New chat")).not.toBeInTheDocument();
    });
  });

  describe("Branding", () => {
    it("should render branding section when ENABLE_PUBLISH is true", () => {
      // Arrange
      mockEnablePublish = true;

      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(screen.getByText("Built with Langflow")).toBeInTheDocument();
      expect(screen.getByText("Theme")).toBeInTheDocument();
      expect(screen.getByTestId("theme-buttons")).toBeInTheDocument();
      expect(screen.getByTestId("langflow-logo-color")).toBeInTheDocument();
    });

    it("should not render branding section when ENABLE_PUBLISH is false", () => {
      // Arrange
      mockEnablePublish = false;

      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(screen.queryByText("Built with Langflow")).not.toBeInTheDocument();
      expect(screen.queryByText("Theme")).not.toBeInTheDocument();
    });
  });

  describe("Chat Header", () => {
    it("should pass isFullscreen as true to ChatHeader", () => {
      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(capturedHeaderProps.isFullscreen).toBe(true);
    });

    it("should not pass onToggleFullscreen to ChatHeader", () => {
      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(capturedHeaderProps.onToggleFullscreen).toBeUndefined();
    });

    it("should not pass onClose to ChatHeader", () => {
      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(capturedHeaderProps.onClose).toBeUndefined();
    });

    it("should pass currentFlowId to ChatHeader", () => {
      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(capturedHeaderProps.currentFlowId).toBe("flow-123");
    });
  });

  describe("Session Management", () => {
    it("should call addNewSession when onNewChat is triggered", () => {
      // Arrange
      render(<ShareablePlaygroundContent />);

      // Act
      act(() => {
        (capturedSidebarProps.onNewChat as () => void)();
      });

      // Assert
      expect(mockAddNewSession).toHaveBeenCalledWith(
        expect.arrayContaining(["flow-123"]),
      );
    });

    it("should call handleDelete and removeLocalSession when deleting a session", () => {
      // Arrange
      render(<ShareablePlaygroundContent />);

      // Act
      act(() => {
        (capturedSidebarProps.onDeleteSession as (id: string) => void)(
          "session-2",
        );
      });

      // Assert
      expect(mockHandleDelete).toHaveBeenCalledWith("session-2");
      expect(mockRemoveLocalSession).toHaveBeenCalledWith("session-2");
    });
  });

  describe("Core Components", () => {
    it("should always render ChatInput", () => {
      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(screen.getByTestId("chat-input")).toBeInTheDocument();
    });

    it("should always render ChatSidebar", () => {
      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(screen.getByTestId("chat-sidebar")).toBeInTheDocument();
    });

    it("should always render ChatHeader", () => {
      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      expect(screen.getByTestId("chat-header")).toBeInTheDocument();
    });
  });

  describe("Ordered Sessions", () => {
    it("should pass currentFlowId as first session to ChatSidebar", () => {
      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      const sessions = capturedSidebarProps.sessions as string[];
      expect(sessions[0]).toBe("flow-123");
    });

    it("should deduplicate sessions", () => {
      // Act
      render(<ShareablePlaygroundContent />);

      // Assert
      const sessions = capturedSidebarProps.sessions as string[];
      const uniqueSessions = new Set(sessions);
      expect(sessions.length).toBe(uniqueSessions.size);
    });
  });
});
