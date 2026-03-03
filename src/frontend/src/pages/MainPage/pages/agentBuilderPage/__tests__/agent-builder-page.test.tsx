/**
 * Tests for the AgentBuilderPage component.
 *
 * Covers: rendering, agent list, agent selection, create/edit flow.
 */

// ── Mocks ────────────────────────────────────────────────────────
const mockAgents = [
  {
    id: "agent-1",
    name: "Alpha Agent",
    description: "First agent",
    system_prompt: "Be helpful",
    tool_components: ["Calculator"],
    icon: null,
    user_id: "user-1",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "agent-2",
    name: "Beta Agent",
    description: null,
    system_prompt: "Be concise",
    tool_components: [],
    icon: null,
    user_id: "user-1",
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
];

const mockCreateAgent = jest.fn();
const mockUpdateAgent = jest.fn();
const mockSetSelectedAgentId = jest.fn();

jest.mock("@/controllers/API/queries/agents", () => ({
  useGetAgents: () => ({ data: mockAgents, isLoading: false }),
  useCreateAgent: () => ({ mutate: mockCreateAgent }),
  useUpdateAgent: () => ({ mutate: mockUpdateAgent }),
  useGetAgentTools: () => ({ data: [] }),
}));

const mockStoreState = {
  selectedAgentId: null as string | null,
  setSelectedAgentId: (id: string | null) => {
    mockStoreState.selectedAgentId = id;
    mockSetSelectedAgentId(id);
  },
};

jest.mock("@/stores/agentBuilderStore", () => {
  const store = jest.fn(
    (selector?: (s: typeof mockStoreState) => unknown) =>
      typeof selector === "function"
        ? selector(mockStoreState)
        : mockStoreState,
  );
  store.getState = () => mockStoreState;
  store.setState = jest.fn();
  store.subscribe = jest.fn();
  return { __esModule: true, default: store };
});

jest.mock("@/components/common/genericIconComponent", () => {
  const fn = ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  );
  fn.displayName = "ForwardedIconComponent";
  return { __esModule: true, default: fn };
});

jest.mock("@/components/ui/sidebar", () => ({
  SidebarTrigger: ({ children }: { children: React.ReactNode }) => (
    <button data-testid="sidebar-trigger">{children}</button>
  ),
}));

// Mock AgentChatPanel to avoid ModelSelector/QueryClient dependency
jest.mock("../components/AgentChatPanel", () => ({
  AgentChatPanel: ({
    agent,
    onEditAgent,
  }: {
    agent: { id: string; name: string };
    onEditAgent: (a: unknown) => void;
  }) => (
    <div data-testid="agent-chat-panel">
      <span data-testid="chat-agent-name">{agent.name}</span>
      <button
        data-testid="chat-edit-button"
        onClick={() => onEditAgent(agent)}
      >
        Edit
      </button>
    </div>
  ),
}));

// Mock AgentEmptyState
jest.mock("../components/AgentEmptyState", () => ({
  AgentEmptyState: ({
    onCreateAgent,
  }: {
    onCreateAgent: () => void;
  }) => (
    <div data-testid="agent-empty-state">
      <button data-testid="empty-state-create" onClick={onCreateAgent}>
        Create Agent
      </button>
    </div>
  ),
}));

jest.mock(
  "@/modals/agentBuilderModal/AgentBuilderModal",
  () => ({
    AgentBuilderModal: ({
      isOpen,
      onClose,
      onSave,
      isEditing,
    }: {
      isOpen: boolean;
      onClose: () => void;
      onSave: (data: unknown) => void;
      isEditing: boolean;
    }) =>
      isOpen ? (
        <div data-testid="agent-modal">
          <span data-testid="modal-mode">
            {isEditing ? "edit" : "create"}
          </span>
          <button
            data-testid="modal-save"
            onClick={() =>
              onSave({
                name: "Test",
                description: "",
                systemPrompt: "Hi",
                selectedTools: [],
              })
            }
          >
            Save
          </button>
          <button data-testid="modal-close" onClick={onClose}>
            Close
          </button>
        </div>
      ) : null,
  }),
);

// ── Imports ──────────────────────────────────────────────────────
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { AgentBuilderPage } from "../agent-builder-page";

// ── Tests ────────────────────────────────────────────────────────
describe("AgentBuilderPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStoreState.selectedAgentId = null;
  });

  describe("Rendering", () => {
    it("renders the page wrapper", () => {
      render(<AgentBuilderPage />);
      expect(screen.getByTestId("agent-builder-wrapper")).toBeInTheDocument();
    });

    it("renders header with Agent Builder title", () => {
      render(<AgentBuilderPage />);
      expect(screen.getByText("Agent Builder")).toBeInTheDocument();
    });

    it("renders agent list items", () => {
      render(<AgentBuilderPage />);
      expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
      expect(screen.getByText("Beta Agent")).toBeInTheDocument();
    });

    it("renders empty state when no agent is selected", () => {
      render(<AgentBuilderPage />);
      expect(screen.getByTestId("agent-empty-state")).toBeInTheDocument();
    });
  });

  describe("Agent selection", () => {
    it("calls setSelectedAgentId when agent card is clicked", async () => {
      const user = userEvent.setup();
      render(<AgentBuilderPage />);

      await user.click(screen.getByTestId("agent-card-agent-1"));

      expect(mockSetSelectedAgentId).toHaveBeenCalledWith("agent-1");
    });
  });

  describe("Create agent flow", () => {
    it("opens modal in create mode via list create button", async () => {
      const user = userEvent.setup();
      render(<AgentBuilderPage />);

      await user.click(screen.getByTestId("create-agent-button"));

      await waitFor(() => {
        expect(screen.getByTestId("agent-modal")).toBeInTheDocument();
      });
      expect(screen.getByTestId("modal-mode")).toHaveTextContent("create");
    });

    it("opens modal via empty state create button", async () => {
      const user = userEvent.setup();
      render(<AgentBuilderPage />);

      await user.click(screen.getByTestId("empty-state-create"));

      await waitFor(() => {
        expect(screen.getByTestId("agent-modal")).toBeInTheDocument();
      });
    });

    it("calls createAgent and closes modal on save", async () => {
      const user = userEvent.setup();
      render(<AgentBuilderPage />);

      // Open modal
      await user.click(screen.getByTestId("create-agent-button"));

      await waitFor(() => {
        expect(screen.getByTestId("agent-modal")).toBeInTheDocument();
      });

      // Save
      await user.click(screen.getByTestId("modal-save"));

      expect(mockCreateAgent).toHaveBeenCalledTimes(1);
      await waitFor(() => {
        expect(screen.queryByTestId("agent-modal")).not.toBeInTheDocument();
      });
    });

    it("closes modal on cancel without saving", async () => {
      const user = userEvent.setup();
      render(<AgentBuilderPage />);

      await user.click(screen.getByTestId("create-agent-button"));

      await waitFor(() => {
        expect(screen.getByTestId("agent-modal")).toBeInTheDocument();
      });

      await user.click(screen.getByTestId("modal-close"));

      await waitFor(() => {
        expect(screen.queryByTestId("agent-modal")).not.toBeInTheDocument();
      });
      expect(mockCreateAgent).not.toHaveBeenCalled();
    });
  });

  describe("Adversarial", () => {
    it("handles multiple rapid clicks on agent cards", async () => {
      const user = userEvent.setup();
      render(<AgentBuilderPage />);

      await user.click(screen.getByTestId("agent-card-agent-1"));
      await user.click(screen.getByTestId("agent-card-agent-2"));
      await user.click(screen.getByTestId("agent-card-agent-1"));

      expect(mockSetSelectedAgentId).toHaveBeenCalledTimes(3);
    });

    it("handles rapid modal open-close-open", async () => {
      const user = userEvent.setup();
      render(<AgentBuilderPage />);

      // Open
      await user.click(screen.getByTestId("create-agent-button"));
      await waitFor(() => {
        expect(screen.getByTestId("agent-modal")).toBeInTheDocument();
      });

      // Close
      await user.click(screen.getByTestId("modal-close"));
      await waitFor(() => {
        expect(screen.queryByTestId("agent-modal")).not.toBeInTheDocument();
      });

      // Re-open
      await user.click(screen.getByTestId("create-agent-button"));
      await waitFor(() => {
        expect(screen.getByTestId("agent-modal")).toBeInTheDocument();
      });
    });
  });
});
