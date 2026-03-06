import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AssistantInput } from "../assistant-input";

// --- Mocks ---

jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIcon({ name }: { name: string }) {
    return <span data-testid={`icon-${name}`} />;
  };
});

jest.mock("../model-selector", () => ({
  ModelSelector: () => <div data-testid="model-selector" />,
}));

jest.mock("../../helpers/messages", () => ({
  getRandomPlaceholderMessage: () => "Processing your request...",
}));

jest.mock("../../assistant-panel.constants", () => ({
  getAssistantPlaceholder: () => "Ask me anything about Langflow...",
}));

describe("AssistantInput", () => {
  const defaultProps = {
    onSend: jest.fn(),
    onStop: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  describe("rendering", () => {
    it("should render textarea with idle placeholder", () => {
      render(<AssistantInput {...defaultProps} />);

      expect(
        screen.getByPlaceholderText("Ask me anything about Langflow..."),
      ).toBeInTheDocument();
    });

    it("should render model selector", () => {
      render(<AssistantInput {...defaultProps} />);

      expect(screen.getByTestId("model-selector")).toBeInTheDocument();
    });

    it("should render send button when not processing", () => {
      render(<AssistantInput {...defaultProps} />);

      expect(
        screen.getByRole("button", { name: /send message/i }),
      ).toBeInTheDocument();
    });

    it("should render stop button when processing", () => {
      render(<AssistantInput {...defaultProps} isProcessing={true} />);

      expect(
        screen.getByRole("button", { name: /stop generation/i }),
      ).toBeInTheDocument();
    });
  });

  describe("placeholder behavior", () => {
    it("should show 'Working on it...' during generating steps", () => {
      render(
        <AssistantInput
          {...defaultProps}
          isProcessing={true}
          currentStep="generating"
        />,
      );

      expect(
        screen.getByPlaceholderText("Working on it..."),
      ).toBeInTheDocument();
    });

    it("should show empty placeholder during post-generation steps", () => {
      render(
        <AssistantInput
          {...defaultProps}
          isProcessing={true}
          currentStep="validating"
        />,
      );

      // Post-generation steps clear the native placeholder to show animated overlay
      expect(screen.getByRole("textbox")).toHaveAttribute("placeholder", "");
    });
  });

  describe("keyboard interactions", () => {
    it("should send message on Enter key", async () => {
      const onSend = jest.fn();
      render(<AssistantInput {...defaultProps} onSend={onSend} />);

      const textarea = screen.getByRole("textbox");
      await userEvent.type(textarea, "hello{enter}");

      expect(onSend).toHaveBeenCalledTimes(1);
      expect(onSend).toHaveBeenCalledWith("hello", null);
    });

    it("should not send on Shift+Enter", async () => {
      const onSend = jest.fn();
      render(<AssistantInput {...defaultProps} onSend={onSend} />);

      const textarea = screen.getByRole("textbox");
      await userEvent.type(textarea, "hello{shift>}{enter}{/shift}");

      expect(onSend).not.toHaveBeenCalled();
    });

    it("should blur textarea on Escape", async () => {
      render(<AssistantInput {...defaultProps} />);

      const textarea = screen.getByRole("textbox");
      await userEvent.click(textarea);
      expect(textarea).toHaveFocus();

      await userEvent.keyboard("{Escape}");

      expect(textarea).not.toHaveFocus();
    });
  });

  describe("send button state", () => {
    it("should be disabled when message is empty", () => {
      render(<AssistantInput {...defaultProps} />);

      expect(
        screen.getByRole("button", { name: /send message/i }),
      ).toBeDisabled();
    });

    it("should be disabled when disabled prop is true", async () => {
      render(<AssistantInput {...defaultProps} disabled={true} />);

      // Even with text typed, the button should be disabled
      expect(
        screen.getByRole("button", { name: /send message/i }),
      ).toBeDisabled();
    });

    it("should be enabled when message has content and not disabled", async () => {
      render(<AssistantInput {...defaultProps} />);

      await userEvent.type(screen.getByRole("textbox"), "hello");

      expect(
        screen.getByRole("button", { name: /send message/i }),
      ).toBeEnabled();
    });
  });

  describe("stop button", () => {
    it("should call onStop when clicked during processing", async () => {
      const onStop = jest.fn();
      render(
        <AssistantInput
          {...defaultProps}
          onStop={onStop}
          isProcessing={true}
        />,
      );

      await userEvent.click(
        screen.getByRole("button", { name: /stop generation/i }),
      );

      expect(onStop).toHaveBeenCalledTimes(1);
    });
  });

  describe("message clearing", () => {
    it("should clear textarea after sending", async () => {
      render(<AssistantInput {...defaultProps} />);

      const textarea = screen.getByRole("textbox");
      await userEvent.type(textarea, "hello{enter}");

      expect(textarea).toHaveValue("");
    });

    it("should not send whitespace-only messages", async () => {
      const onSend = jest.fn();
      render(<AssistantInput {...defaultProps} onSend={onSend} />);

      const textarea = screen.getByRole("textbox");
      await userEvent.type(textarea, "   {enter}");

      expect(onSend).not.toHaveBeenCalled();
    });
  });
});
