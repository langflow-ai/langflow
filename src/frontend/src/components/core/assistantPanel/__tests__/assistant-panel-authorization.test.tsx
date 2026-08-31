import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AssistantPanel } from "../assistant-panel";
import type { AssistantModel } from "../assistant-panel.types";

const SAVED_MODEL: AssistantModel = {
  id: "OpenAI-gpt-4o",
  name: "gpt-4o",
  provider: "OpenAI",
  displayName: "gpt-4o",
};

const mockHandleSend = jest.fn();
const mockClearPendingMessage = jest.fn();
const mockSetAssistantProcessing = jest.fn();
let mockCatalogReady = true;
let mockHasEnabledModels = true;
let mockModelAllowed = true;
let mockPendingMessage: string | null = null;

const mockIsModelEnabled = (model: AssistantModel | null) =>
  mockModelAllowed &&
  model?.provider === SAVED_MODEL.provider &&
  model.name === SAVED_MODEL.name;

jest.mock("@/components/ui/sidebar", () => ({
  useSidebar: () => ({ open: false }),
}));

jest.mock("@/contexts/permissionsContext", () => ({
  useIsFlowReadOnly: () => false,
}));

jest.mock("@/stores/assistantManagerStore", () => ({
  __esModule: true,
  default: (
    selector: (state: { setAssistantProcessing: jest.Mock }) => unknown,
  ) => selector({ setAssistantProcessing: mockSetAssistantProcessing }),
}));

jest.mock("@/stores/flowBuilderWelcomeStore", () => ({
  __esModule: true,
  default: (
    selector: (state: {
      pendingMessage: string | null;
      clearPendingMessage: jest.Mock;
    }) => unknown,
  ) =>
    selector({
      pendingMessage: mockPendingMessage,
      clearPendingMessage: mockClearPendingMessage,
    }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: { currentFlow: { id: string } }) => unknown) =>
    selector({ currentFlow: { id: "flow-1" } }),
}));

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (
    selector: (state: { agenticExperienceEnabled: boolean }) => unknown,
  ) => selector({ agenticExperienceEnabled: true }),
}));

jest.mock("use-stick-to-bottom", () => {
  const StickToBottom = ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  );
  StickToBottom.Content = ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  );
  return {
    StickToBottom,
    useStickToBottomContext: () => ({ scrollToBottom: jest.fn() }),
  };
});

jest.mock("../components/assistant-header", () => ({
  AssistantHeader: () => <div data-testid="assistant-header" />,
}));

jest.mock("../components/assistant-message", () => ({
  AssistantMessageItem: () => null,
}));

jest.mock("../components/assistant-disabled-state", () => ({
  AssistantDisabledState: () => <div data-testid="assistant-disabled-state" />,
}));

jest.mock("../components/assistant-no-models-state", () => ({
  AssistantNoModelsState: () => <div data-testid="assistant-no-models-state" />,
}));

jest.mock("../components/assistant-input", () => ({
  AssistantInput: ({
    onSend,
    disabled,
  }: {
    onSend: (content: string, model: AssistantModel | null) => void;
    disabled: boolean;
  }) => (
    <button
      type="button"
      data-testid="mock-assistant-send"
      disabled={disabled}
      onClick={() => onSend("direct message", SAVED_MODEL)}
    >
      Send
    </button>
  ),
}));

jest.mock("../hooks", () => ({
  useEnabledModels: () => ({
    hasEnabledModels: mockHasEnabledModels,
    isCatalogReady: mockCatalogReady,
    isLoading: !mockCatalogReady,
    isError: false,
    isModelEnabled: (model: AssistantModel | null) => mockIsModelEnabled(model),
  }),
  useAssistantChat: () => ({
    messages: [],
    sessionId: "session-1",
    isProcessing: false,
    currentStep: null,
    handleSend: mockHandleSend,
    handleApprove: jest.fn(),
    handleUpdateFlowAction: jest.fn(),
    handleApplyFlowProposal: jest.fn(),
    handleRevertFlowProposal: jest.fn(),
    handleDismissFlowProposal: jest.fn(),
    handleApprovePlan: jest.fn(),
    handleDismissPlan: jest.fn(),
    handleResetPlan: jest.fn(),
    handleAcknowledgeValidation: jest.fn(),
    isRefiningPlan: false,
    skipAll: false,
    handleRetry: jest.fn(),
    handleMarkReverted: jest.fn(),
    handleStopGeneration: jest.fn(),
    handleClearHistory: jest.fn(),
    loadSession: jest.fn(),
  }),
  useSessionHistory: () => ({
    sessions: [],
    saveCurrentSession: jest.fn(),
    switchSession: jest.fn(),
    deleteSession: jest.fn(),
  }),
}));

describe("AssistantPanel scoped model authorization", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    localStorage.setItem(
      "langflow-assistant-selected-model",
      JSON.stringify(SAVED_MODEL),
    );
    mockCatalogReady = true;
    mockHasEnabledModels = true;
    mockModelAllowed = true;
    mockPendingMessage = null;
  });

  it("keeps a pending welcome message until the current flow catalog is ready", async () => {
    mockCatalogReady = false;
    mockPendingMessage = "build a flow";

    const { rerender } = render(<AssistantPanel isOpen onClose={jest.fn()} />);

    expect(mockHandleSend).not.toHaveBeenCalled();
    expect(mockClearPendingMessage).not.toHaveBeenCalled();

    mockCatalogReady = true;
    rerender(<AssistantPanel isOpen onClose={jest.fn()} />);
    await waitFor(() => expect(mockHandleSend).toHaveBeenCalled());
  });

  it("rejects a stale localStorage model when auto-sending after a scope switch", async () => {
    mockModelAllowed = false;
    mockPendingMessage = "build a flow";

    const { rerender } = render(<AssistantPanel isOpen onClose={jest.fn()} />);

    expect(mockHandleSend).not.toHaveBeenCalled();
    expect(mockClearPendingMessage).not.toHaveBeenCalled();

    mockModelAllowed = true;
    rerender(<AssistantPanel isOpen onClose={jest.fn()} />);
    await waitFor(() => expect(mockHandleSend).toHaveBeenCalled());
  });

  it("guards direct panel sends with current catalog membership", async () => {
    mockModelAllowed = false;
    const user = userEvent.setup();

    render(<AssistantPanel isOpen onClose={jest.fn()} />);

    // The real AssistantInput disables its own send button from the same
    // catalog hook. Invoke the mocked child anyway to verify the panel keeps
    // an independent authorization boundary around the callback.
    await user.click(screen.getByTestId("mock-assistant-send"));
    expect(mockHandleSend).not.toHaveBeenCalled();
  });

  it("renders the composer disabled while scoped policy is still loading", () => {
    mockCatalogReady = false;
    mockHasEnabledModels = false;

    render(<AssistantPanel isOpen onClose={jest.fn()} />);

    expect(screen.getByTestId("mock-assistant-send")).toBeDisabled();
    expect(screen.queryByTestId("assistant-no-models-state")).toBeNull();
  });
});
