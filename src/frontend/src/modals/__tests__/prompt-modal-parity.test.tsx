import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MustachePromptModal from "../mustachePromptModal";
import PromptModal from "../promptModal";

// Mock the API hook
const mockMutate = jest.fn();
jest.mock("@/controllers/API/queries/nodes/use-post-validate-prompt", () => ({
  usePostValidatePrompt: () => ({
    mutate: mockMutate,
  }),
}));

// Mock alert store
const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetNoticeData = jest.fn();

interface AlertState {
  setSuccessData: typeof mockSetSuccessData;
  setErrorData: typeof mockSetErrorData;
  setNoticeData: typeof mockSetNoticeData;
}

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: <T,>(selector: (state: AlertState) => T): T => {
    const state: AlertState = {
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
      setNoticeData: mockSetNoticeData,
    };
    return selector(state);
  },
}));

// Mock IconComponent
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

// Mock SanitizedHTMLWrapper
jest.mock("@/components/common/sanitizedHTMLWrapper", () => {
  const React = require("react");
  return React.forwardRef(function MockSanitizedHTMLWrapper(
    {
      content,
      className,
      onClick,
    }: { content: string; className?: string; onClick?: () => void },
    ref: React.ForwardedRef<HTMLDivElement>,
  ) {
    return (
      <div
        ref={ref}
        data-testid="sanitized-html"
        className={className}
        onClick={onClick}
        onKeyDown={onClick}
        role="button"
        tabIndex={0}
        dangerouslySetInnerHTML={{ __html: content }}
      />
    );
  });
});

// Mock ShadTooltip
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content: string;
  }) => <div data-tooltip={content}>{children}</div>,
}));

// Mock BaseModal
jest.mock("@/modals/baseModal", () => {
  const React = require("react");

  interface ChildrenProps {
    children: React.ReactNode;
  }

  interface HeaderProps extends ChildrenProps {
    description?: string;
  }

  interface TriggerProps extends ChildrenProps {
    disable?: boolean;
    asChild?: boolean;
  }

  interface BaseModalProps extends ChildrenProps {
    open?: boolean;
    setOpen?: (open: boolean) => void;
    size?: string;
  }

  interface ReactChild {
    type?: {
      displayName?: string;
    };
  }

  const MockContent = ({ children }: ChildrenProps) => (
    <div data-testid="modal-content">{children}</div>
  );
  const MockHeader = ({ children, description }: HeaderProps) => (
    <div data-testid="modal-header" data-description={description}>
      {children}
    </div>
  );
  const MockTrigger = ({ children, disable }: TriggerProps) => (
    <div data-testid="modal-trigger" data-disabled={disable}>
      {children}
    </div>
  );
  const MockFooter = ({ children }: ChildrenProps) => (
    <div data-testid="modal-footer">{children}</div>
  );

  function MockBaseModal({ children, open, setOpen, size }: BaseModalProps) {
    // Only render children when open
    if (!open) {
      // Still render the trigger so we can click it
      const trigger = React.Children.toArray(children).find(
        (child: ReactChild) => child?.type?.displayName === "Trigger",
      );
      return (
        <div data-testid="base-modal-closed">
          {trigger}
          <button data-testid="mock-open-modal" onClick={() => setOpen?.(true)}>
            Open Modal
          </button>
        </div>
      );
    }

    return (
      <div data-testid="base-modal" data-size={size}>
        {children}
      </div>
    );
  }

  MockContent.displayName = "Content";
  MockHeader.displayName = "Header";
  MockTrigger.displayName = "Trigger";
  MockFooter.displayName = "Footer";

  MockBaseModal.Content = MockContent;
  MockBaseModal.Header = MockHeader;
  MockBaseModal.Trigger = MockTrigger;
  MockBaseModal.Footer = MockFooter;

  return { __esModule: true, default: MockBaseModal };
});

// Mock varHighlightHTML (shared by both modals)
jest.mock("@/modals/promptModal/utils/var-highlight-html", () => ({
  __esModule: true,
  default: ({
    name,
    addCurlyBraces,
  }: {
    name: string;
    addCurlyBraces: boolean;
  }) => `<span class="highlighted">${name}</span>`,
}));

// Mock reactflowUtils
jest.mock("@/utils/reactflowUtils", () => ({
  handleKeyDown: jest.fn(),
}));

type SyntaxCase = {
  label: string;
  Component: typeof PromptModal | typeof MustachePromptModal;
  /** wraps a variable name in this syntax's braces */
  wrap: (name: string) => string;
  /** whether the validate payload must carry the mustache flag */
  expectsMustacheFlag: boolean;
};

const syntaxes: SyntaxCase[] = [
  {
    label: "fstring (PromptModal)",
    Component: PromptModal,
    wrap: (name) => `{${name}}`,
    expectsMustacheFlag: false,
  },
  {
    label: "mustache (MustachePromptModal)",
    Component: MustachePromptModal,
    wrap: (name) => `{{${name}}}`,
    expectsMustacheFlag: true,
  },
];

describe.each(syntaxes)(
  "prompt modal parity — $label",
  ({ Component, wrap, expectsMustacheFlag }) => {
    const defaultProps = {
      field_name: "template",
      value: "",
      setValue: jest.fn(),
      nodeClass: {
        template: {
          template: { value: "" },
        },
      },
      setNodeClass: jest.fn(),
      children: <button data-testid="trigger">Open</button>,
      disabled: false,
      id: "test-modal",
      readonly: false,
    };

    beforeEach(() => {
      jest.clearAllMocks();
      mockMutate.mockClear();
      mockSetSuccessData.mockClear();
      mockSetErrorData.mockClear();
      mockSetNoticeData.mockClear();
    });

    describe("rendering", () => {
      it("should render the modal trigger", () => {
        render(<Component {...defaultProps} />);
        expect(screen.getByTestId("modal-trigger")).toBeInTheDocument();
      });

      it("should render modal content when open", () => {
        render(<Component {...defaultProps} />);

        fireEvent.click(screen.getByTestId("mock-open-modal"));

        expect(screen.getByTestId("modal-content")).toBeInTheDocument();
        expect(screen.getByTestId("modal-header")).toBeInTheDocument();
        expect(screen.getByTestId("modal-footer")).toBeInTheDocument();
      });

      it("should display Edit Prompt title", () => {
        render(<Component {...defaultProps} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        expect(screen.getByTestId("modal-title")).toHaveTextContent(
          "Edit Prompt",
        );
      });

      it("should render with initial value", () => {
        render(<Component {...defaultProps} value={`Hello ${wrap("name")}`} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const textarea = screen.getByTestId("modal-test-modal");
        expect(textarea).toHaveValue(`Hello ${wrap("name")}`);
      });
    });

    describe("variable extraction", () => {
      it("should extract variables and display as badges", () => {
        render(
          <Component
            {...defaultProps}
            value={`Hello ${wrap("name")}, welcome to ${wrap("place")}!`}
          />,
        );
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        expect(screen.getByText("name")).toBeInTheDocument();
        expect(screen.getByText("place")).toBeInTheDocument();
      });

      it("should deduplicate variables", () => {
        render(
          <Component
            {...defaultProps}
            value={`${wrap("name")} and ${wrap("name")} and ${wrap("name")}`}
          />,
        );
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const badges = screen.getAllByText("name");
        expect(badges).toHaveLength(1);
      });

      it("should not extract an unclosed brace as a variable", () => {
        const unclosed = wrap("name").slice(0, -1); // strip one closing brace
        render(<Component {...defaultProps} value={`Hello ${unclosed}`} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        expect(screen.queryByText("name")).not.toBeInTheDocument();
      });
    });

    describe("textarea editing", () => {
      it("should update input value when typing", async () => {
        render(<Component {...defaultProps} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const textarea = screen.getByTestId("modal-test-modal");
        // Use fireEvent.change since userEvent.type treats { as special chars
        fireEvent.change(textarea, {
          target: { value: `Hello ${wrap("world")}` },
        });

        expect(textarea).toHaveValue(`Hello ${wrap("world")}`);
      });

      it("should update variables when input changes", async () => {
        render(<Component {...defaultProps} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const textarea = screen.getByTestId("modal-test-modal");
        fireEvent.change(textarea, {
          target: { value: wrap("new_var") },
        });

        expect(screen.getByText("new_var")).toBeInTheDocument();
      });
    });

    describe("validation and saving", () => {
      it("should call validatePrompt with the syntax's payload when save is clicked", async () => {
        const user = userEvent.setup();
        render(<Component {...defaultProps} value={`Hello ${wrap("name")}`} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const saveButton = screen.getByTestId("genericModalBtnSave");
        await user.click(saveButton);

        expect(mockMutate).toHaveBeenCalledWith(
          expect.objectContaining({
            name: "template",
            template: `Hello ${wrap("name")}`,
          }),
          expect.any(Object),
        );
        const payload = mockMutate.mock.calls[0][0];
        if (expectsMustacheFlag) {
          expect(payload.mustache).toBe(true);
        } else {
          expect(payload).not.toHaveProperty("mustache");
        }
      });

      it("should call setValue on successful validation", async () => {
        const mockSetValue = jest.fn();
        const mockSetNodeClass = jest.fn();

        mockMutate.mockImplementation((data, options) => {
          options.onSuccess({
            frontend_node: {
              template: { template: { value: data.template } },
            },
            input_variables: ["name"],
          });
        });

        const user = userEvent.setup();
        render(
          <Component
            {...defaultProps}
            value={`Hello ${wrap("name")}`}
            setValue={mockSetValue}
            setNodeClass={mockSetNodeClass}
          />,
        );
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const saveButton = screen.getByTestId("genericModalBtnSave");
        await user.click(saveButton);

        expect(mockSetValue).toHaveBeenCalledWith(`Hello ${wrap("name")}`);
        expect(mockSetSuccessData).toHaveBeenCalled();
      });

      it("should show notice when no input variables are found", async () => {
        mockMutate.mockImplementation((data, options) => {
          options.onSuccess({
            frontend_node: {
              template: { template: { value: data.template } },
            },
            input_variables: [],
          });
        });

        const user = userEvent.setup();
        render(<Component {...defaultProps} value="Hello world" />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const saveButton = screen.getByTestId("genericModalBtnSave");
        await user.click(saveButton);

        expect(mockSetNoticeData).toHaveBeenCalled();
      });

      it("should show error on validation failure", async () => {
        mockMutate.mockImplementation((data, options) => {
          options.onError({
            response: {
              data: {
                detail: "Validation failed",
              },
            },
          });
        });

        const user = userEvent.setup();
        render(<Component {...defaultProps} value={`Hello ${wrap("name")}`} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const saveButton = screen.getByTestId("genericModalBtnSave");
        await user.click(saveButton);

        expect(mockSetErrorData).toHaveBeenCalledWith(
          expect.objectContaining({
            list: expect.arrayContaining(["Validation failed"]),
          }),
        );
      });

      it("should show bug alert when apiReturn is empty", async () => {
        mockMutate.mockImplementation((data, options) => {
          options.onSuccess(null);
        });

        const user = userEvent.setup();
        render(<Component {...defaultProps} value={`Hello ${wrap("name")}`} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const saveButton = screen.getByTestId("genericModalBtnSave");
        await user.click(saveButton);

        expect(mockSetErrorData).toHaveBeenCalled();
      });
    });

    describe("readonly mode", () => {
      it("should disable save button when readonly", () => {
        render(<Component {...defaultProps} readonly={true} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const saveButton = screen.getByTestId("genericModalBtnSave");
        expect(saveButton).toBeDisabled();
      });
    });

    describe("edit/preview mode toggle", () => {
      it("should start in edit mode", () => {
        render(<Component {...defaultProps} value="test" />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const textarea = screen.getByTestId("modal-test-modal");
        expect(textarea).toBeInTheDocument();
      });

      it("should switch to preview mode on blur", async () => {
        render(<Component {...defaultProps} value={`Hello ${wrap("name")}`} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const textarea = screen.getByTestId("modal-test-modal");
        fireEvent.blur(textarea);

        await waitFor(() => {
          expect(screen.getByTestId("sanitized-html")).toBeInTheDocument();
        });
      });

      it("should switch back to edit mode when clicking preview", async () => {
        render(<Component {...defaultProps} value={`Hello ${wrap("name")}`} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const textarea = screen.getByTestId("modal-test-modal");
        fireEvent.blur(textarea);

        await waitFor(() => {
          expect(screen.getByTestId("sanitized-html")).toBeInTheDocument();
        });

        fireEvent.click(screen.getByTestId("sanitized-html"));

        await waitFor(() => {
          expect(screen.getByTestId("modal-test-modal")).toBeInTheDocument();
        });
      });
    });

    describe("CSS class computation", () => {
      it("should use code-nohighlight class for short variable names", () => {
        render(
          <Component {...defaultProps} value={`${wrap("a")} ${wrap("b")}`} />,
        );
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const textarea = screen.getByTestId("modal-test-modal");
        fireEvent.blur(textarea);

        const preview = screen.getByTestId("sanitized-html");
        expect(preview.className).toContain("code-nohighlight");
      });
    });

    describe("badge truncation", () => {
      it("should truncate long variable names in badges", () => {
        const longVarName = "a".repeat(70); // Over 59 characters
        render(<Component {...defaultProps} value={wrap(longVarName)} />);
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const badge = screen.getByText(/\.\.\.$/);
        expect(badge).toBeInTheDocument();
      });
    });

    describe("value synchronization", () => {
      it("should sync inputValue when value prop changes", () => {
        const { rerender } = render(
          <Component {...defaultProps} value="initial" />,
        );
        fireEvent.click(screen.getByTestId("mock-open-modal"));

        const textarea = screen.getByTestId("modal-test-modal");
        expect(textarea).toHaveValue("initial");

        rerender(<Component {...defaultProps} value="updated" />);

        expect(textarea).toHaveValue("updated");
      });
    });
  },
);

describe("fstring-specific behavior (PromptModal)", () => {
  const defaultProps = {
    field_name: "template",
    value: "",
    setValue: jest.fn(),
    nodeClass: {
      template: {
        template: { value: "" },
      },
    },
    setNodeClass: jest.fn(),
    children: <button data-testid="trigger">Open</button>,
    disabled: false,
    id: "test-modal",
    readonly: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should treat escaped double braces as literals, not variables", () => {
    // {{name}} is an even brace run in f-string syntax = escaped literal
    render(<PromptModal {...defaultProps} value="Hello {{name}}" />);
    fireEvent.click(screen.getByTestId("mock-open-modal"));

    expect(screen.queryByText("name")).not.toBeInTheDocument();
  });

  it("should treat odd balanced brace runs as variables", () => {
    // {{{name}}} is an odd (3) balanced run = a variable in f-string syntax
    render(<PromptModal {...defaultProps} value="Hello {{{name}}}" />);
    fireEvent.click(screen.getByTestId("mock-open-modal"));

    expect(screen.getByText("name")).toBeInTheDocument();
  });
});

describe("mustache-specific behavior (MustachePromptModal)", () => {
  const defaultProps = {
    field_name: "template",
    value: "",
    setValue: jest.fn(),
    nodeClass: {
      template: {
        template: { value: "" },
      },
    },
    setNodeClass: jest.fn(),
    children: <button data-testid="trigger">Open</button>,
    disabled: false,
    id: "test-modal",
    readonly: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should not extract invalid variable patterns", () => {
    render(
      <MustachePromptModal
        {...defaultProps}
        value="Invalid: {{123abc}} {{with space}}"
      />,
    );
    fireEvent.click(screen.getByTestId("mock-open-modal"));

    expect(screen.queryByText("123abc")).not.toBeInTheDocument();
    expect(screen.queryByText("with space")).not.toBeInTheDocument();
  });

  it("should treat double braces as variables, not escapes", () => {
    render(<MustachePromptModal {...defaultProps} value="Hello {{name}}" />);
    fireEvent.click(screen.getByTestId("mock-open-modal"));

    expect(screen.getByText("name")).toBeInTheDocument();
  });
});
