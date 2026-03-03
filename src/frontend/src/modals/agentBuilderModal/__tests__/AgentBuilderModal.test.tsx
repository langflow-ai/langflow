/**
 * Tests for the AgentBuilderModal component.
 *
 * Covers: rendering, form fields, submit validation, tool selector, edit mode.
 */

// ── Mocks ────────────────────────────────────────────────────────
const mockTools = [
  {
    class_name: "CalculatorComponent",
    display_name: "Calculator",
    description: "Math ops",
    icon: "Calculator",
    category: "tools",
    is_suggested: true,
  },
  {
    class_name: "URLComponent",
    display_name: "URL Fetcher",
    description: "Fetch URLs",
    icon: "Link",
    category: "utilities",
    is_suggested: false,
  },
];

jest.mock("@/controllers/API/queries/agents", () => ({
  useGetAgentTools: () => ({ data: mockTools }),
}));

jest.mock("@/components/common/genericIconComponent", () => {
  const fn = ({ name }: { name: string }) => <span data-testid={`icon-${name}`} />;
  fn.displayName = "ForwardedIconComponent";
  return { __esModule: true, default: fn };
});

// ── Imports ──────────────────────────────────────────────────────
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { AgentBuilderModal } from "../AgentBuilderModal";
import type { AgentBuilderModalProps } from "../agent-builder-modal-types";

// ── Wrapper ──────────────────────────────────────────────────────
function renderModal(props: AgentBuilderModalProps) {
  return render(
    <TooltipProvider>
      <AgentBuilderModal {...props} />
    </TooltipProvider>,
  );
}

// ── Tests ────────────────────────────────────────────────────────
describe("AgentBuilderModal", () => {
  const defaultProps: AgentBuilderModalProps = {
    isOpen: true,
    onClose: jest.fn(),
    onSave: jest.fn(),
    isEditing: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Rendering", () => {
    it("renders modal when open", () => {
      renderModal({ ...defaultProps });
      expect(screen.getByTestId("agent-builder-modal")).toBeInTheDocument();
    });

    it("shows Create title when not editing", () => {
      renderModal({ ...defaultProps });
      expect(screen.getByText("Create Agent")).toBeInTheDocument();
    });

    it("shows Edit title when editing", () => {
      renderModal({ ...defaultProps, isEditing: true });
      expect(screen.getByText("Edit Agent")).toBeInTheDocument();
    });

    it("renders all form fields", () => {
      renderModal({ ...defaultProps });
      expect(screen.getByTestId("agent-name-input")).toBeInTheDocument();
      expect(screen.getByTestId("agent-description-input")).toBeInTheDocument();
      expect(screen.getByTestId("agent-prompt-input")).toBeInTheDocument();
      expect(screen.getByTestId("tool-search-input")).toBeInTheDocument();
    });

    it("renders Cancel and Create buttons", () => {
      renderModal({ ...defaultProps });
      expect(
        screen.getByRole("button", { name: /cancel/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /create/i }),
      ).toBeInTheDocument();
    });

    it("renders Save button when editing", () => {
      renderModal({ ...defaultProps, isEditing: true });
      expect(
        screen.getByRole("button", { name: /save/i }),
      ).toBeInTheDocument();
    });
  });

  describe("Form defaults", () => {
    it("starts with empty name and description", () => {
      renderModal({ ...defaultProps });
      expect(screen.getByTestId("agent-name-input")).toHaveValue("");
      expect(screen.getByTestId("agent-description-input")).toHaveValue("");
    });

    it("starts with default system prompt", () => {
      renderModal({ ...defaultProps });
      expect(screen.getByTestId("agent-prompt-input")).toHaveValue(
        "You are a helpful assistant that can use tools to answer questions and perform tasks.",
      );
    });

    it("populates fields from initialData", () => {
      renderModal({
        ...defaultProps,
        initialData: {
          name: "Test Agent",
          description: "Test desc",
          systemPrompt: "Be concise.",
          selectedTools: ["CalculatorComponent"],
        },
      });
      expect(screen.getByTestId("agent-name-input")).toHaveValue("Test Agent");
      expect(screen.getByTestId("agent-description-input")).toHaveValue(
        "Test desc",
      );
      expect(screen.getByTestId("agent-prompt-input")).toHaveValue(
        "Be concise.",
      );
    });
  });

  describe("Validation", () => {
    it("disables submit when name is empty", () => {
      renderModal({ ...defaultProps });
      expect(screen.getByTestId("save-agent-button")).toBeDisabled();
    });

    it("disables submit when name is only whitespace", async () => {
      const user = userEvent.setup();
      renderModal({ ...defaultProps });

      await user.type(screen.getByTestId("agent-name-input"), "   ");
      expect(screen.getByTestId("save-agent-button")).toBeDisabled();
    });

    it("enables submit once name is provided", async () => {
      const user = userEvent.setup();
      renderModal({ ...defaultProps });

      await user.type(screen.getByTestId("agent-name-input"), "Bot");
      expect(screen.getByTestId("save-agent-button")).not.toBeDisabled();
    });
  });

  describe("Form submission", () => {
    it("calls onSave with form data on submit", async () => {
      const onSave = jest.fn();
      const user = userEvent.setup();

      renderModal({ ...defaultProps, onSave });

      await user.type(screen.getByTestId("agent-name-input"), "My Bot");
      await user.type(
        screen.getByTestId("agent-description-input"),
        "A cool bot",
      );
      await user.click(screen.getByTestId("save-agent-button"));

      expect(onSave).toHaveBeenCalledTimes(1);
      const data = onSave.mock.calls[0][0];
      expect(data.name).toBe("My Bot");
      expect(data.description).toBe("A cool bot");
      expect(data.selectedTools).toEqual([]);
    });

    it("trims name and description before saving", async () => {
      const onSave = jest.fn();
      const user = userEvent.setup();

      renderModal({ ...defaultProps, onSave });

      await user.type(screen.getByTestId("agent-name-input"), "  Bot  ");
      await user.type(
        screen.getByTestId("agent-description-input"),
        "  Desc  ",
      );
      await user.click(screen.getByTestId("save-agent-button"));

      const data = onSave.mock.calls[0][0];
      expect(data.name).toBe("Bot");
      expect(data.description).toBe("Desc");
    });

    it("does not call onSave when name is empty", async () => {
      const onSave = jest.fn();
      const user = userEvent.setup();

      renderModal({ ...defaultProps, onSave });

      // Button is disabled but simulate a forced click
      await user.click(screen.getByTestId("save-agent-button"));
      expect(onSave).not.toHaveBeenCalled();
    });

    it("calls onClose when Cancel is clicked", async () => {
      const onClose = jest.fn();
      const user = userEvent.setup();

      renderModal({ ...defaultProps, onClose });

      await user.click(screen.getByRole("button", { name: /cancel/i }));
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe("Tool selector", () => {
    it("shows suggested tools by default", () => {
      renderModal({ ...defaultProps });
      expect(screen.getByText("Calculator")).toBeInTheDocument();
    });

    it("filters tools when search is used", async () => {
      const user = userEvent.setup();
      renderModal({ ...defaultProps });

      await user.type(screen.getByTestId("tool-search-input"), "URL");

      expect(screen.getByText("URL Fetcher")).toBeInTheDocument();
    });

    it("shows no results message for non-matching search", async () => {
      const user = userEvent.setup();
      renderModal({ ...defaultProps });

      await user.type(
        screen.getByTestId("tool-search-input"),
        "nonexistent-tool",
      );

      expect(screen.getByText("No components found")).toBeInTheDocument();
    });

    it("toggles tool selection on click", async () => {
      const onSave = jest.fn();
      const user = userEvent.setup();

      renderModal({ ...defaultProps, onSave });

      // Select Calculator
      await user.click(screen.getByText("Calculator"));

      // Fill name then submit
      await user.type(screen.getByTestId("agent-name-input"), "Bot");
      await user.click(screen.getByTestId("save-agent-button"));

      expect(onSave.mock.calls[0][0].selectedTools).toEqual([
        "CalculatorComponent",
      ]);
    });

    it("deselects tool on second click", async () => {
      const onSave = jest.fn();
      const user = userEvent.setup();

      renderModal({ ...defaultProps, onSave });

      // Select Calculator
      await user.click(screen.getByText("Calculator"));

      // After selection, "Calculator" appears both in chip and list.
      // Click the chip (which has the X icon) to deselect.
      const chip = screen.getByTestId("icon-X").closest("button")!;
      await user.click(chip);

      await user.type(screen.getByTestId("agent-name-input"), "Bot");
      await user.click(screen.getByTestId("save-agent-button"));

      expect(onSave.mock.calls[0][0].selectedTools).toEqual([]);
    });
  });

  describe("Adversarial", () => {
    it("handles rapid typing in name field", async () => {
      const user = userEvent.setup();
      renderModal({ ...defaultProps });

      await user.type(
        screen.getByTestId("agent-name-input"),
        "fast-typing-test",
      );

      expect(screen.getByTestId("agent-name-input")).toHaveValue(
        "fast-typing-test",
      );
    });

    it("preserves system prompt when only name changes", async () => {
      const onSave = jest.fn();
      const user = userEvent.setup();
      const customPrompt = "Custom system prompt.";

      renderModal({
        ...defaultProps,
        onSave,
        initialData: {
          name: "Agent",
          description: "",
          systemPrompt: customPrompt,
          selectedTools: [],
        },
      });

      await user.clear(screen.getByTestId("agent-name-input"));
      await user.type(screen.getByTestId("agent-name-input"), "New Name");
      await user.click(screen.getByTestId("save-agent-button"));

      expect(onSave.mock.calls[0][0].systemPrompt).toBe(customPrompt);
    });

    it("handles special characters in name", async () => {
      const onSave = jest.fn();
      const user = userEvent.setup();

      renderModal({ ...defaultProps, onSave });

      await user.type(
        screen.getByTestId("agent-name-input"),
        'Agent <"test"> & Co.',
      );
      await user.click(screen.getByTestId("save-agent-button"));

      expect(onSave.mock.calls[0][0].name).toBe('Agent <"test"> & Co.');
    });
  });
});
