import { render, screen } from "@testing-library/react";
import type { AssistantMessage } from "../../assistant-panel.types";
import { AssistantMessageItem } from "../assistant-message";

// --- Mocks ---

jest.mock("@/contexts/authContext", () => ({
  AuthContext: {
    _currentValue: {
      userData: { profile_image: "Space/046-rocket.svg" },
    },
  },
}));

// Mock React.useContext to provide auth data
const mockUseContext = jest.fn();
jest
  .spyOn(require("react"), "useContext")
  .mockImplementation((ctx: unknown) => {
    // Return auth context mock for AuthContext
    const authCtx = require("@/contexts/authContext").AuthContext;
    if (ctx === authCtx) {
      return { userData: { profile_image: "Space/046-rocket.svg" } };
    }
    return mockUseContext(ctx);
  });

jest.mock("@/customization/config-constants", () => ({
  BASE_URL_API: "http://localhost:7860/api/v1/",
}));

// Mocking the customization layer for the user avatar is how we prove the
// Desktop Langflow Assistant avatar bug is fixed: the component must render
// CustomProfileIcon (which the Desktop customization overrides to prepend an
// absolute baseURL), not a bare <img> with a relative URL.
jest.mock("@/customization/components/custom-profile-icon", () => ({
  CustomProfileIcon: ({ className }: { className?: string }) => (
    <img
      data-testid="custom-profile-icon"
      data-classname={className}
      alt="User"
    />
  ),
}));

jest.mock("@/assets/langflow_assistant.svg", () => "langflow-icon.svg");

jest.mock("../assistant-component-result", () => ({
  AssistantComponentResult: ({
    result,
    onApprove,
  }: {
    result: { className?: string };
    onApprove: () => void;
  }) => (
    <div data-testid="component-result">
      <span>{result.className}</span>
      <button onClick={onApprove}>Approve</button>
    </div>
  ),
}));

jest.mock("../assistant-loading-state", () => ({
  AssistantLoadingState: () => <div data-testid="loading-state" />,
  default: () => <div data-testid="loading-state" />,
}));

// FileContentModal pulls SanitizedMarkdown → rehype-mathjax/raw/sanitize, all
// ESM-only. We mock it to a minimal stand-in so the loading-state /
// writtenFiles branches can be tested without dragging the ESM chain.
jest.mock("../file-content-modal", () => ({
  __esModule: true,
  FileContentModal: ({ path, open }: { path: string; open: boolean }) =>
    open ? <div data-testid={`file-content-modal-${path}`} /> : null,
}));

jest.mock("../assistant-validation-failed", () => ({
  AssistantValidationFailed: ({
    result,
    onRetry,
  }: {
    result: { validationError?: string };
    onRetry?: () => void;
  }) => (
    <div data-testid="validation-failed">
      {result.validationError}
      {onRetry && (
        <button data-testid="retry-button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  ),
}));

jest.mock("../../helpers/messages", () => ({
  getRandomThinkingMessage: () => "Thinking...",
}));

jest.mock("react-markdown", () => {
  return function MockMarkdown({ children }: { children: string }) {
    return <div data-testid="markdown-content">{children}</div>;
  };
});

jest.mock("remark-gfm", () => () => {});

jest.mock("@/components/core/codeTabsComponent", () => {
  return function MockCodeTab({ code }: { code: string }) {
    return <pre data-testid="code-tab">{code}</pre>;
  };
});

jest.mock("@/utils/codeBlockUtils", () => ({
  extractLanguage: () => "python",
  isCodeBlock: () => false,
}));

jest.mock("@/components/common/messageMetadataComponent", () => ({
  __esModule: true,
  default: ({
    usage,
    duration,
  }: {
    usage?: {
      input_tokens?: number;
      output_tokens?: number;
      total_tokens?: number;
    };
    duration?: number;
  }) => {
    const hasTokens =
      typeof usage?.total_tokens === "number" && usage.total_tokens > 0;
    const hasDuration = typeof duration === "number" && duration > 0;
    if (!hasTokens && !hasDuration) return null;
    return (
      <span
        data-testid="chat-message-token-usage"
        data-total-tokens={usage?.total_tokens ?? ""}
        data-input-tokens={usage?.input_tokens ?? ""}
        data-output-tokens={usage?.output_tokens ?? ""}
        data-duration={duration ?? ""}
      />
    );
  },
}));

function createMessage(overrides: Partial<AssistantMessage>): AssistantMessage {
  return {
    id: "msg-1",
    role: "assistant",
    content: "",
    timestamp: new Date(),
    status: "complete",
    ...overrides,
  };
}

describe("AssistantMessageItem", () => {
  describe("user messages", () => {
    it("should render user message with profile image", () => {
      const message = createMessage({
        role: "user",
        content: "Build a component",
        status: "complete",
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.getByText("User")).toBeInTheDocument();
      expect(screen.getByAltText("User")).toBeInTheDocument();
    });

    // Regression guard: Langflow Desktop shipped with a broken user avatar in
    // the Assistant panel because the bare <img> used a relative URL that
    // resolved against the Tauri origin instead of the Python sidecar. The
    // fix routes the avatar through CustomProfileIcon so Desktop's
    // customization override prepends the absolute baseURL. If someone later
    // replaces CustomProfileIcon with an inline <img> again, this test fails.
    it("should_render_user_avatar_via_custom_profile_icon_when_message_is_from_user", () => {
      const message = createMessage({
        role: "user",
        content: "Build a component",
        status: "complete",
      });

      render(<AssistantMessageItem message={message} />);

      const avatar = screen.getByTestId("custom-profile-icon");
      expect(avatar).toBeInTheDocument();
      // The h-7 sizing must be forwarded through the className prop so the
      // Desktop override can honor the Assistant panel's avatar size.
      expect(avatar.getAttribute("data-classname")).toContain("h-7");
      expect(avatar.getAttribute("data-classname")).toContain("w-7");
      expect(avatar.getAttribute("data-classname")).toContain("rounded-full");
    });

    it("should render user message content", () => {
      const message = createMessage({
        role: "user",
        content: "Create a RAG pipeline",
        status: "complete",
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.getByTestId("markdown-content")).toHaveTextContent(
        "Create a RAG pipeline",
      );
    });
  });

  describe("assistant messages", () => {
    it("should render assistant label with Langflow icon", () => {
      const message = createMessage({
        role: "assistant",
        content: "Here is your component",
        status: "complete",
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.getByText("Langflow Assistant")).toBeInTheDocument();
      expect(screen.getByAltText("Langflow Assistant")).toBeInTheDocument();
    });
  });

  describe("streaming state", () => {
    it("should show thinking indicator when streaming with no content", () => {
      const message = createMessage({
        role: "assistant",
        content: "",
        status: "streaming",
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.getByText("Thinking...")).toBeInTheDocument();
    });

    it("should show loading state during component generation", () => {
      const message = createMessage({
        role: "assistant",
        content: "",
        status: "streaming",
        progress: {
          step: "generating_component",
          attempt: 0,
          maxAttempts: 3,
        },
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    });

    it("should show the rich loading state during the 'orchestrating' step (compound pipeline)", () => {
      // A compound (component_then_flow) request must surface the rich
      // "Orchestrating..." indicator, NOT the generic thinking dots.
      const message = createMessage({
        role: "assistant",
        content: "",
        status: "streaming",
        progress: {
          step: "orchestrating",
          message: "Orchestrating...",
          attempt: 0,
          maxAttempts: 3,
        },
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.getByTestId("loading-state")).toBeInTheDocument();
      expect(screen.queryByText("Thinking...")).toBeNull();
    });

    it("should show the rich loading state during 'generating_document' step (parity with component/flow)", () => {
      // UX requirement change (user request): documents must get the SAME
      // rich UI as generating_component / generating_flow — not the
      // generic dotted "Generating document..." thinking line. The earlier
      // anti-glitch concern (a bordered streaming card morphing into the
      // file card) is addressed by using the icon-only minimal mode
      // (animated Langflow glyph), NOT the bordered streaming card — see
      // the assistant-loading-state icon-mode test.
      const message = createMessage({
        role: "assistant",
        content: "",
        status: "streaming",
        progress: {
          step: "generating_document",
          attempt: 0,
          maxAttempts: 3,
          message: "Generating document...",
        },
      });

      render(<AssistantMessageItem message={message} />);

      // Rich loading state mounts (it renders icon-only mode internally).
      expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    });

    it("should render the file card stack when no progress is present (fall-through after Continue)", () => {
      // When `validationAnimationComplete` has flipped, the parent stops
      // passing `progress` to drive the loading state. We model that exit
      // condition by passing a message WITHOUT progress: writtenFiles must
      // then render directly (the post-Continue branch). This pinpoints the
      // render branch without juggling jest.doMock + dynamic imports.
      const message = createMessage({
        role: "assistant",
        content: "",
        status: "complete",
        writtenFiles: [
          {
            action: "write_file",
            path: "DOCS.md",
            size: 100,
            receivedAt: 1,
          },
        ],
      });

      render(<AssistantMessageItem message={message} />);

      expect(
        screen.getByTestId("assistant-file-card-DOCS.md"),
      ).toBeInTheDocument();
    });

    it("should render the file card immediately when writtenFiles arrive (no Continue gate for documents)", () => {
      // The manage_files path is intentionally gateless — the action is
      // non-destructive (the file is already on disk in the user's sandbox)
      // and the agent's text response gives enough context. The card jumps
      // straight to its final state.
      const message = createMessage({
        role: "assistant",
        content: "Created the DOCS.md file.",
        status: "complete",
        progress: {
          step: "generating_document",
          attempt: 0,
          maxAttempts: 3,
          message: "Generating document...",
        },
        writtenFiles: [
          {
            action: "write_file",
            path: "DOCS.md",
            size: 100,
            receivedAt: 1,
            content: "# hi",
          },
        ],
      });

      render(<AssistantMessageItem message={message} />);

      expect(
        screen.getByTestId("assistant-file-card-DOCS.md"),
      ).toBeInTheDocument();
      // The loading state must NOT be mounted once we're at the final state.
      expect(screen.queryByTestId("loading-state")).toBeNull();
    });

    it("should detect component code in streaming content with progress", () => {
      const message = createMessage({
        role: "assistant",
        content:
          "```python\nfrom langflow.custom import Component\n\nclass MyComponent(Component):\n    pass\n```",
        status: "streaming",
        progress: {
          step: "generating",
          attempt: 0,
          maxAttempts: 3,
        },
      });

      render(<AssistantMessageItem message={message} />);

      // Content matches component code regex AND has progress, so loading state is shown
      expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    });
  });

  describe("error state", () => {
    it("should show error message", () => {
      const message = createMessage({
        role: "assistant",
        content: "",
        status: "error",
        error: "API key is invalid",
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.getByText("API key is invalid")).toBeInTheDocument();
    });
  });

  describe("cancelled state", () => {
    it("should show 'Cancelled' text", () => {
      const message = createMessage({
        role: "assistant",
        content: "",
        status: "cancelled",
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.getByText("Cancelled")).toBeInTheDocument();
    });
  });

  describe("validated component result", () => {
    it("should show component result for validated response", () => {
      const message = createMessage({
        role: "assistant",
        content: "Here is your component",
        status: "complete",
        result: {
          content: "Here is your component",
          validated: true,
          className: "MyComponent",
          componentCode: "class MyComponent(Component): pass",
        },
      });

      render(<AssistantMessageItem message={message} onApprove={jest.fn()} />);

      expect(screen.getByTestId("component-result")).toBeInTheDocument();
      expect(screen.getByText("MyComponent")).toBeInTheDocument();
    });
  });

  describe("validation failed", () => {
    it("should show validation failure for failed validation", () => {
      const message = createMessage({
        role: "assistant",
        content: "",
        status: "complete",
        result: {
          content: "",
          validated: false,
          validationError: "SyntaxError: invalid syntax",
        },
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.getByTestId("validation-failed")).toBeInTheDocument();
      expect(
        screen.getByText("SyntaxError: invalid syntax"),
      ).toBeInTheDocument();
    });

    it("should_show_retry_button_when_validation_fails", () => {
      // Bug: AssistantValidationFailed is rendered without onRetry prop,
      // so the "Try again" button never appears.
      const message = createMessage({
        role: "assistant",
        content: "",
        status: "complete",
        result: {
          content: "",
          validated: false,
          validationError: "SyntaxError: invalid syntax",
          componentCode: "class Bad(Component): pass",
        },
      });

      const onRetry = jest.fn();
      render(<AssistantMessageItem message={message} onRetry={onRetry} />);

      expect(screen.getByTestId("retry-button")).toBeInTheDocument();
    });
  });

  describe("plain text response", () => {
    it("should render markdown for regular text content", () => {
      const message = createMessage({
        role: "assistant",
        content: "Langflow is a visual flow builder.",
        status: "complete",
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.getByTestId("markdown-content")).toHaveTextContent(
        "Langflow is a visual flow builder.",
      );
    });

    it("should_render_markdown_when_qa_response_contains_example_component_code", () => {
      // Bug: User asks "how do I create a custom component?" and the LLM
      // responds with explanation + example code. The frontend regex fallback
      // detects "class SumComponent(Component)" in the example and renders
      // a component card instead of the text answer.
      const qaWithExampleCode = [
        "To create a custom component:\n\n",
        "1. Create a Python file\n",
        "2. Define a class extending Component\n\n",
        "```python\n",
        "from lfx.custom import Component\n",
        "from lfx.io import Output\n",
        "from lfx.schema import Data\n\n",
        "class SumComponent(Component):\n",
        "    display_name = 'Sum'\n",
        "    inputs = []\n",
        "    outputs = [Output(name='result', display_name='Result', method='run')]\n\n",
        "    def run(self) -> Data:\n",
        "        return Data(data={'result': 42})\n",
        "```\n\n",
        "Save the file and restart Langflow.",
      ].join("");

      const message = createMessage({
        role: "assistant",
        content: qaWithExampleCode,
        status: "complete",
        // No result — this is a Q&A response, not a component generation
      });

      render(<AssistantMessageItem message={message} />);

      // Should render as markdown text, NOT as a component card
      expect(screen.getByTestId("markdown-content")).toBeInTheDocument();
      expect(screen.queryByTestId("component-result")).not.toBeInTheDocument();
    });
  });

  describe("hidden flag", () => {
    it("should_render_nothing_when_message_is_hidden", () => {
      // Skip-all sets `hidden: true` on the propose_plan turn so its
      // preamble doesn't pollute the chat. The renderer must opt out
      // entirely — returning even an empty bubble would leave a gap.
      const message = createMessage({
        role: "assistant",
        content: "I proposed a plan and am waiting.",
        status: "complete",
        hidden: true,
      });

      const { container } = render(<AssistantMessageItem message={message} />);

      expect(container).toBeEmptyDOMElement();
    });
  });

  describe("skipApprovalGate prop (skip-all mode)", () => {
    it("should_render_component_result_immediately_when_skipApprovalGate_true_and_result_validated", () => {
      // With the gate skipped, validationAnimationComplete starts true so
      // the user sees the final component card without a Continue click.
      const message = createMessage({
        role: "assistant",
        status: "complete",
        content: "",
        progress: {
          step: "validated",
          attempt: 0,
          maxAttempts: 3,
          message: "Validated",
          componentCode: "class X: pass",
          className: "X",
        },
        result: {
          content: "",
          validated: true,
          componentCode: "class X: pass",
          className: "X",
        },
      });

      render(
        <AssistantMessageItem message={message} skipApprovalGate={true} />,
      );

      expect(screen.getByTestId("component-result")).toBeInTheDocument();
      // The loading-state Continue gate must NOT be on screen.
      expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    });

    it("should_keep_loading_state_when_skipApprovalGate_false_and_result_validated", () => {
      // Regression baseline: without skip, the Continue gate stays mounted
      // until the user clicks Continue.
      const message = createMessage({
        role: "assistant",
        status: "complete",
        content: "",
        progress: {
          step: "validated",
          attempt: 0,
          maxAttempts: 3,
          message: "Validated",
          componentCode: "class X: pass",
          className: "X",
        },
        result: {
          content: "",
          validated: true,
          componentCode: "class X: pass",
          className: "X",
        },
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.getByTestId("loading-state")).toBeInTheDocument();
      expect(screen.queryByTestId("component-result")).not.toBeInTheDocument();
    });
  });

  // Bug: `if (message.hidden) return null` ran BEFORE useState/useMemo.
  // Skip-all flips a rendered message to hidden, changing the hook count
  // between renders — React: "Rendered fewer hooks than during the
  // previous render", crashing the whole panel.
  describe("hidden flag — hooks order (crash regression)", () => {
    it("should_render_nothing_for_hidden_then_content_when_unhidden_without_crashing", () => {
      const { container, rerender } = render(
        <AssistantMessageItem
          message={createMessage({
            id: "msg-1",
            content: "Working on the flow...",
            status: "streaming",
            hidden: true,
          })}
        />,
      );
      // Hidden: the guard still suppresses all output.
      expect(container).toBeEmptyDOMElement();

      expect(() =>
        rerender(
          <AssistantMessageItem
            message={createMessage({
              id: "msg-1",
              content: "Working on the flow...",
              status: "complete",
            })}
          />,
        ),
      ).not.toThrow();
      // Unhidden on the SAME fiber: content renders (hooks stayed stable).
      expect(screen.getByText("Working on the flow...")).toBeInTheDocument();
    });
  });

  describe("token usage badge", () => {
    it("should_render_token_usage_badge_when_assistant_message_has_usage", () => {
      const message = createMessage({
        role: "assistant",
        content: "Done.",
        status: "complete",
        usage: { input_tokens: 110, output_tokens: 54, total_tokens: 164 },
        duration: 1234,
      });

      render(<AssistantMessageItem message={message} />);

      const badge = screen.getByTestId("chat-message-token-usage");
      expect(badge).toBeInTheDocument();
      expect(badge.getAttribute("data-total-tokens")).toBe("164");
      expect(badge.getAttribute("data-input-tokens")).toBe("110");
      expect(badge.getAttribute("data-output-tokens")).toBe("54");
      expect(badge.getAttribute("data-duration")).toBe("1234");
    });

    it("should_not_render_token_usage_badge_when_assistant_message_has_no_usage", () => {
      const message = createMessage({
        role: "assistant",
        content: "Done.",
        status: "complete",
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.queryByTestId("chat-message-token-usage")).toBeNull();
    });

    it("should_not_render_token_usage_badge_for_user_messages_even_if_usage_present", () => {
      // User messages never carry cost in this product (cost is the
      // assistant's calls). Defensive: even if a user message somehow
      // gets a ``usage`` payload, the badge must not appear on it.
      const message = createMessage({
        role: "user",
        content: "Hi",
        status: "complete",
        usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2 },
        duration: 500,
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.queryByTestId("chat-message-token-usage")).toBeNull();
    });

    it("should_not_render_token_usage_badge_while_assistant_message_is_streaming", () => {
      // The badge belongs to the final cost of a turn — flashing a
      // half-aggregated number mid-stream would be misleading.
      const message = createMessage({
        role: "assistant",
        content: "Working...",
        status: "streaming",
        usage: { input_tokens: 50, output_tokens: 0, total_tokens: 50 },
        duration: 200,
      });

      render(<AssistantMessageItem message={message} />);

      expect(screen.queryByTestId("chat-message-token-usage")).toBeNull();
    });
  });
});
