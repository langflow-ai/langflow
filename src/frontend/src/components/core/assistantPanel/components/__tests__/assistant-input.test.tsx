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
    it("should show 'Generating response...' during 'generating' step (Q&A)", () => {
      render(
        <AssistantInput
          {...defaultProps}
          isProcessing={true}
          currentStep="generating"
        />,
      );

      expect(
        screen.getByPlaceholderText("Generating response..."),
      ).toBeInTheDocument();
    });

    it("should show 'Generating component...' during 'generating_component' step", () => {
      render(
        <AssistantInput
          {...defaultProps}
          isProcessing={true}
          currentStep="generating_component"
        />,
      );

      expect(
        screen.getByPlaceholderText("Generating component..."),
      ).toBeInTheDocument();
    });

    it("should show 'Generating flow...' during 'generating_flow' step", () => {
      // Regression: 'generating_flow' must behave like the other generating
      // steps (no rotating placeholder, static intent-specific text) so the
      // user sees a stable label instead of cycling random messages.
      render(
        <AssistantInput
          {...defaultProps}
          isProcessing={true}
          currentStep="generating_flow"
        />,
      );

      expect(
        screen.getByPlaceholderText("Generating flow..."),
      ).toBeInTheDocument();
    });

    it("should show 'Orchestrating...' during 'orchestrating' step (compound request)", () => {
      // A multi-ask prompt runs the single agent loop; the user must see a
      // real indicator, not a generic rotating "Thinking..." placeholder.
      render(
        <AssistantInput
          {...defaultProps}
          isProcessing={true}
          currentStep="orchestrating"
        />,
      );

      expect(
        screen.getByPlaceholderText("Orchestrating..."),
      ).toBeInTheDocument();
    });

    it("should show 'Generating document...' during 'generating_document' step", () => {
      // Regression guard: the manage_files intent must render a STATIC
      // intent-specific placeholder instead of falling back to the rotating
      // animated placeholder ("Confirming component structure...", etc.) —
      // mirrors the generating_flow / generating_component behavior.
      render(
        <AssistantInput
          {...defaultProps}
          isProcessing={true}
          currentStep="generating_document"
        />,
      );

      expect(
        screen.getByPlaceholderText("Generating document..."),
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

    it("should show refining placeholder when isRefiningPlan is true and not processing", () => {
      // When the user dismissed a plan and is composing the refinement, we
      // override the idle placeholder with a directed cue so the input
      // reads as "this is the box where I tell the agent what to change".
      render(<AssistantInput {...defaultProps} isRefiningPlan={true} />);

      expect(
        screen.getByPlaceholderText("Tell me what to change…"),
      ).toBeInTheDocument();
    });

    it("should not show refining placeholder while a generating step is active", () => {
      // The generating-step placeholder takes precedence — refining only
      // overrides the idle placeholder, not the in-progress UX.
      render(
        <AssistantInput
          {...defaultProps}
          isRefiningPlan={true}
          isProcessing={true}
          currentStep="generating_flow"
        />,
      );

      expect(
        screen.getByPlaceholderText("Generating flow..."),
      ).toBeInTheDocument();
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
      // canSend requires a selectedModel — pre-populate localStorage so the
      // input boots with a model and matches the production contract that
      // ModelSelector's auto-select effect normally satisfies.
      localStorage.setItem(
        "langflow-assistant-selected-model",
        JSON.stringify({
          id: "OpenAI-gpt-4o",
          name: "gpt-4o",
          provider: "OpenAI",
          displayName: "GPT-4o",
        }),
      );
      render(<AssistantInput {...defaultProps} />);

      await userEvent.type(screen.getByRole("textbox"), "hello");

      expect(
        screen.getByRole("button", { name: /send message/i }),
      ).toBeEnabled();
    });

    it("should stay disabled when message has content but no model is selected", async () => {
      // Regression guard for the canSend gate (assistant-input.tsx:231): the
      // send button MUST stay disabled until a model is selected, even if the
      // user has typed text. Without this, the click can fire before
      // ModelSelector's auto-select propagates and use-assistant-chat
      // early-returns silently — see the Playwright assistant-panel race fix.
      render(<AssistantInput {...defaultProps} />);

      await userEvent.type(screen.getByRole("textbox"), "hello");

      expect(
        screen.getByRole("button", { name: /send message/i }),
      ).toBeDisabled();
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

  describe("draft persistence", () => {
    it("should_initialize_with_draft_message_when_provided", () => {
      // Bug: input text is lost when closing and reopening the panel.
      // The draftMessage prop allows restoring previously typed text.
      render(<AssistantInput {...defaultProps} draftMessage="saved draft" />);

      expect(screen.getByRole("textbox")).toHaveValue("saved draft");
    });

    it("should_call_onDraftChange_when_user_types", async () => {
      const onDraftChange = jest.fn();
      render(
        <AssistantInput {...defaultProps} onDraftChange={onDraftChange} />,
      );

      await userEvent.type(screen.getByRole("textbox"), "hi");

      expect(onDraftChange).toHaveBeenCalledWith("h");
      expect(onDraftChange).toHaveBeenCalledWith("hi");
    });

    it("should_clear_draft_on_send", async () => {
      const onDraftChange = jest.fn();
      render(
        <AssistantInput
          {...defaultProps}
          draftMessage="to send"
          onDraftChange={onDraftChange}
        />,
      );

      await userEvent.type(screen.getByRole("textbox"), "{enter}");

      expect(onDraftChange).toHaveBeenLastCalledWith("");
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

  describe("command history (arrow-up / arrow-down)", () => {
    const STORAGE_KEY = "langflow-assistant-input-history";

    beforeEach(() => {
      localStorage.clear();
    });

    function seedHistory(entries: string[]) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    }

    it("should_recall_latest_input_when_arrow_up_pressed_with_empty_textarea", async () => {
      seedHistory(["latest command"]);
      render(<AssistantInput {...defaultProps} />);

      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      textarea.focus();
      await userEvent.keyboard("{ArrowUp}");

      expect(textarea).toHaveValue("latest command");
    });

    it("should_walk_to_older_entries_on_subsequent_arrow_ups", async () => {
      seedHistory(["newest", "middle", "oldest"]);
      render(<AssistantInput {...defaultProps} />);
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      textarea.focus();

      await userEvent.keyboard("{ArrowUp}");
      expect(textarea).toHaveValue("newest");
      await userEvent.keyboard("{ArrowUp}");
      expect(textarea).toHaveValue("middle");
      await userEvent.keyboard("{ArrowUp}");
      expect(textarea).toHaveValue("oldest");
    });

    it("should_walk_back_toward_present_on_arrow_down", async () => {
      seedHistory(["newest", "older"]);
      render(<AssistantInput {...defaultProps} />);
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      textarea.focus();

      await userEvent.keyboard("{ArrowUp}{ArrowUp}");
      expect(textarea).toHaveValue("older");
      await userEvent.keyboard("{ArrowDown}");
      expect(textarea).toHaveValue("newest");
      // One more Down past the newest entry → restore the (empty) draft.
      await userEvent.keyboard("{ArrowDown}");
      expect(textarea).toHaveValue("");
    });

    it("should_push_message_to_history_after_send", async () => {
      const onSend = jest.fn();
      const model = {
        id: "openai/gpt-4",
        name: "gpt-4",
        provider: "openai",
        displayName: "GPT-4",
      };
      // ModelSelector is mocked above — we need onSend to receive a model
      // for AssistantInput's handleSend to call through. Use the model
      // from localStorage trick: prime it.
      localStorage.setItem(
        "langflow-assistant-selected-model",
        JSON.stringify(model),
      );

      render(<AssistantInput {...defaultProps} onSend={onSend} />);
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      await userEvent.type(textarea, "my message{enter}");

      // After send the textarea is empty. Arrow Up should bring back the
      // just-sent message.
      textarea.focus();
      await userEvent.keyboard("{ArrowUp}");
      expect(textarea).toHaveValue("my message");
    });

    it("should_preserve_in_progress_draft_when_navigating_and_coming_back", async () => {
      // The shell convention: pressing Up while typing a draft must not
      // discard the draft. Down past the newest entry restores it.
      seedHistory(["history command"]);
      render(<AssistantInput {...defaultProps} />);
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      await userEvent.type(textarea, "draft text");

      await userEvent.keyboard("{ArrowUp}");
      expect(textarea).toHaveValue("history command");
      await userEvent.keyboard("{ArrowDown}");
      expect(textarea).toHaveValue("draft text");
    });

    it("should_not_trigger_history_when_arrow_up_pressed_mid_textarea_on_multiline_content", async () => {
      // For multiline inputs Up should keep its standard meaning (move
      // cursor up between visual lines). History only kicks in when the
      // cursor is on the first line of the textarea.
      seedHistory(["history command"]);
      render(<AssistantInput {...defaultProps} />);
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      await userEvent.type(textarea, "line one{Shift>}{Enter}{/Shift}line two");
      // Cursor is now at the end of "line two" — i.e. on the SECOND line.

      await userEvent.keyboard("{ArrowUp}");

      // Value did NOT get replaced by history; user keeps editing what
      // they typed.
      expect(textarea).toHaveValue("line one\nline two");
    });
  });
});
