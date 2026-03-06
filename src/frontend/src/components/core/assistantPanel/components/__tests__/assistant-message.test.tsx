import { render, screen } from "@testing-library/react";
import { AssistantMessageItem } from "../assistant-message";
import type { AssistantMessage } from "../../assistant-panel.types";

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
jest.spyOn(require("react"), "useContext").mockImplementation((ctx: unknown) => {
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

jest.mock("../assistant-validation-failed", () => ({
  AssistantValidationFailed: ({
    result,
  }: {
    result: { validationError?: string };
  }) => (
    <div data-testid="validation-failed">{result.validationError}</div>
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

    it("should detect component code in streaming content with progress", () => {
      const message = createMessage({
        role: "assistant",
        content:
          '```python\nfrom langflow.custom import Component\n\nclass MyComponent(Component):\n    pass\n```',
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

      render(
        <AssistantMessageItem
          message={message}
          onApprove={jest.fn()}
        />,
      );

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
  });
});
