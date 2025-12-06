import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";

// Mock all the heavy dependencies first
jest.mock("@/controllers/API/queries/nodes/use-post-validate-prompt", () => ({
  usePostValidatePrompt: () => ({
    mutate: jest.fn(),
  }),
}));

jest.mock("../../baseModal", () => {
  const MockBaseModal = ({ children }: any) => (
    <div data-testid="base-modal">{children}</div>
  );
  MockBaseModal.Trigger = ({ children }: any) => children;
  MockBaseModal.Header = ({ children }: any) => (
    <div data-testid="modal-header">{children}</div>
  );
  MockBaseModal.Content = ({ children }: any) => (
    <div data-testid="modal-content">{children}</div>
  );
  MockBaseModal.Footer = ({ children }: any) => (
    <div data-testid="modal-footer">{children}</div>
  );

  return {
    __esModule: true,
    default: MockBaseModal,
  };
});

jest.mock("../../../components/common/genericIconComponent", () => {
  return function MockIconComponent({ name, className }: any) {
    return <span data-testid={`icon-${name}`} className={className} />;
  };
});

jest.mock("../../../components/ui/button", () => ({
  Button: ({ children, onClick, className, ...props }: any) => (
    <button onClick={onClick} className={className} {...props}>
      {children}
    </button>
  ),
}));

jest.mock("../../../components/ui/textarea", () => ({
  Textarea: React.forwardRef(function MockTextarea(props: any, ref: any) {
    return <textarea ref={ref} {...props} />;
  }),
}));

jest.mock("../../../components/common/sanitizedHTMLWrapper", () => {
  return React.forwardRef(function MockSanitizedHTMLWrapper(
    { content }: any,
    ref: any,
  ) {
    return <div ref={ref} dangerouslySetInnerHTML={{ __html: content }} />;
  });
});

jest.mock("../../../components/common/shadTooltipComponent", () => {
  return function MockShadTooltip({ children, content }: any) {
    return <div title={content}>{children}</div>;
  };
});

jest.mock("../../../components/ui/badge", () => ({
  Badge: ({ children, ...props }: any) => <span {...props}>{children}</span>,
}));

jest.mock("../../../stores/alertStore", () => ({
  __esModule: true,
  default: () => ({
    setSuccessData: jest.fn(),
    setErrorData: jest.fn(),
    setNoticeData: jest.fn(),
  }),
}));

jest.mock("../../../constants/alerts_constants", () => ({
  BUG_ALERT: "Bug Alert",
  PROMPT_ERROR_ALERT: "Prompt Error Alert",
  PROMPT_SUCCESS_ALERT: "Prompt Success Alert",
  TEMP_NOTICE_ALERT: "Temp Notice Alert",
}));

jest.mock("../../../constants/constants", () => ({
  EDIT_TEXT_PLACEHOLDER: "Edit text placeholder",
  INVALID_CHARACTERS: ["<", ">", "&"],
  MAX_WORDS_HIGHLIGHT: 100,
  regexHighlight: /(\{+)([^{}]+)(\}+)/g,
}));

jest.mock("../../../utils/reactflowUtils", () => ({
  handleKeyDown: jest.fn(),
}));

jest.mock("../../../utils/utils", () => ({
  classNames: (...args: any[]) => args.filter(Boolean).join(" "),
}));

jest.mock("../utils/var-highlight-html", () => ({
  __esModule: true,
  default: ({ name }: any) => `<span class="highlighted">{${name}}</span>`,
}));

// Now import the component after all mocks are set up
import PromptModal from "../index";

describe("PromptModal - Add Variable Button", () => {
  const defaultProps = {
    value: "Hello world",
    setValue: jest.fn(),
    nodeClass: {},
    setNodeClass: jest.fn(),
    children: <button>Open Modal</button>,
    id: "test-modal",
    readonly: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should render Add Variable button when not readonly", () => {
    render(<PromptModal {...defaultProps} />);

    const addVariableButton = screen.getByTestId("add-variable-button");
    expect(addVariableButton).toBeInTheDocument();
    expect(addVariableButton).toHaveTextContent("Add Variable");
  });

  it("should not render Add Variable button when readonly", () => {
    render(<PromptModal {...defaultProps} readonly={true} />);

    const addVariableButton = screen.queryByTestId("add-variable-button");
    expect(addVariableButton).not.toBeInTheDocument();
  });

  it("should have Plus icon in Add Variable button", () => {
    render(<PromptModal {...defaultProps} />);

    const plusIcon = screen.getByTestId("icon-Plus");
    expect(plusIcon).toBeInTheDocument();
  });

  it("should insert variable at end of text when clicked", async () => {
    const setValue = jest.fn();
    render(
      <PromptModal {...defaultProps} value="Hello world" setValue={setValue} />,
    );

    const addVariableButton = screen.getByTestId("add-variable-button");
    fireEvent.click(addVariableButton);

    await waitFor(() => {
      // Check that the textarea contains the expected content
      const textarea = screen.getByRole("textbox");
      expect(textarea).toHaveValue("Hello world{variable_name}");
    });
  });

  it("should focus and select variable name after insertion", async () => {
    render(<PromptModal {...defaultProps} value="Test " />);

    const addVariableButton = screen.getByTestId("add-variable-button");
    fireEvent.click(addVariableButton);

    await waitFor(
      () => {
        const textarea = screen.getByRole("textbox");
        expect(textarea).toHaveFocus();
      },
      { timeout: 200 },
    );
  });

  it("should work with empty text", async () => {
    const setValue = jest.fn();
    render(<PromptModal {...defaultProps} value="" setValue={setValue} />);

    const addVariableButton = screen.getByTestId("add-variable-button");
    fireEvent.click(addVariableButton);

    await waitFor(() => {
      // Check that the textarea contains the expected content
      const textarea = screen.getByRole("textbox");
      expect(textarea).toHaveValue("{variable_name}");
    });
  });

  it("should not trigger if readonly", () => {
    const setValue = jest.fn();
    render(
      <PromptModal {...defaultProps} readonly={true} setValue={setValue} />,
    );

    // Button shouldn't exist in readonly mode, but if it did, it shouldn't work
    expect(screen.queryByTestId("add-variable-button")).not.toBeInTheDocument();
    expect(setValue).not.toHaveBeenCalled();
  });

  it("should be positioned absolutely in top-right", () => {
    render(<PromptModal {...defaultProps} />);

    const addVariableButton = screen.getByTestId("add-variable-button");
    expect(addVariableButton).toHaveClass("absolute", "top-3", "right-3");
  });

  it("should have proper styling classes", () => {
    render(<PromptModal {...defaultProps} />);

    const addVariableButton = screen.getByTestId("add-variable-button");
    expect(addVariableButton).toHaveClass(
      "absolute",
      "top-3",
      "right-3",
      "z-10",
      "bg-background/80",
      "backdrop-blur-sm",
    );
  });
});
