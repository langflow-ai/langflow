import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MustachePromptModal from "../index";

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

// Mock varHighlightHTML
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

describe("MustachePromptModal", () => {
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
      render(<MustachePromptModal {...defaultProps} />);
      expect(screen.getByTestId("modal-trigger")).toBeInTheDocument();
    });

    it("should render modal content when open", () => {
      render(<MustachePromptModal {...defaultProps} />);

      // Click to open the modal
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      expect(screen.getByTestId("modal-content")).toBeInTheDocument();
      expect(screen.getByTestId("modal-header")).toBeInTheDocument();
      expect(screen.getByTestId("modal-footer")).toBeInTheDocument();
    });

    it("should display Edit Prompt title", () => {
      render(<MustachePromptModal {...defaultProps} />);
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      expect(screen.getByTestId("modal-title")).toHaveTextContent(
        "Edit Prompt",
      );
    });

    it("should render with initial value", () => {
      render(<MustachePromptModal {...defaultProps} value="Hello {{name}}" />);
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      const textarea = screen.getByTestId("modal-test-modal");
      expect(textarea).toHaveValue("Hello {{name}}");
    });
  });

  describe("variable extraction", () => {
    it("should extract mustache variables and display as badges", () => {
      render(
        <MustachePromptModal
          {...defaultProps}
          value="Hello {{name}}, welcome to {{place}}!"
        />,
      );
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      // Look for badge elements
      expect(screen.getByText("name")).toBeInTheDocument();
      expect(screen.getByText("place")).toBeInTheDocument();
    });

    it("should not extract invalid variable patterns", () => {
      render(
        <MustachePromptModal
          {...defaultProps}
          value="Invalid: {{123abc}} {{with space}}"
        />,
      );
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      // Invalid patterns should not be shown as badges
      expect(screen.queryByText("123abc")).not.toBeInTheDocument();
      expect(screen.queryByText("with space")).not.toBeInTheDocument();
    });

    it("should deduplicate variables", () => {
      render(
        <MustachePromptModal
          {...defaultProps}
          value="{{name}} and {{name}} and {{name}}"
        />,
      );
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      // Should only show one badge for "name"
      const badges = screen.getAllByText("name");
      expect(badges).toHaveLength(1);
    });
  });

  describe("textarea editing", () => {
    it("should update input value when typing", async () => {
      render(<MustachePromptModal {...defaultProps} />);
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      const textarea = screen.getByTestId("modal-test-modal");
      // Use fireEvent.change for mustache syntax since userEvent.type treats { as special chars
      fireEvent.change(textarea, { target: { value: "Hello {{world}}" } });

      expect(textarea).toHaveValue("Hello {{world}}");
    });

    it("should update variables when input changes", async () => {
      render(<MustachePromptModal {...defaultProps} />);
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      const textarea = screen.getByTestId("modal-test-modal");
      // Use fireEvent.change for mustache syntax since userEvent.type treats { as special chars
      fireEvent.change(textarea, { target: { value: "{{new_var}}" } });

      expect(screen.getByText("new_var")).toBeInTheDocument();
    });
  });

  describe("validation and saving", () => {
    it("should call validatePrompt when save button is clicked", async () => {
      const user = userEvent.setup();
      render(<MustachePromptModal {...defaultProps} value="Hello {{name}}" />);
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      const saveButton = screen.getByTestId("genericModalBtnSave");
      await user.click(saveButton);

      expect(mockMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "template",
          template: "Hello {{name}}",
          mustache: true,
        }),
        expect.any(Object),
      );
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
        <MustachePromptModal
          {...defaultProps}
          value="Hello {{name}}"
          setValue={mockSetValue}
          setNodeClass={mockSetNodeClass}
        />,
      );
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      const saveButton = screen.getByTestId("genericModalBtnSave");
      await user.click(saveButton);

      expect(mockSetValue).toHaveBeenCalledWith("Hello {{name}}");
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
      render(<MustachePromptModal {...defaultProps} value="Hello world" />);
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
      render(<MustachePromptModal {...defaultProps} value="Hello {{name}}" />);
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
      render(<MustachePromptModal {...defaultProps} value="Hello {{name}}" />);
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      const saveButton = screen.getByTestId("genericModalBtnSave");
      await user.click(saveButton);

      expect(mockSetErrorData).toHaveBeenCalled();
    });
  });

  describe("readonly mode", () => {
    it("should disable save button when readonly", () => {
      render(<MustachePromptModal {...defaultProps} readonly={true} />);
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      const saveButton = screen.getByTestId("genericModalBtnSave");
      expect(saveButton).toBeDisabled();
    });
  });

  describe("edit/preview mode toggle", () => {
    it("should start in edit mode", () => {
      render(<MustachePromptModal {...defaultProps} value="test" />);
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      // In edit mode, textarea should be visible
      const textarea = screen.getByTestId("modal-test-modal");
      expect(textarea).toBeInTheDocument();
    });

    it("should switch to preview mode on blur", async () => {
      render(<MustachePromptModal {...defaultProps} value="Hello {{name}}" />);
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      const textarea = screen.getByTestId("modal-test-modal");
      fireEvent.blur(textarea);

      // After blur, should show preview (SanitizedHTMLWrapper)
      await waitFor(() => {
        expect(screen.getByTestId("sanitized-html")).toBeInTheDocument();
      });
    });

    it("should switch back to edit mode when clicking preview", async () => {
      render(<MustachePromptModal {...defaultProps} value="Hello {{name}}" />);
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      // Blur to switch to preview
      const textarea = screen.getByTestId("modal-test-modal");
      fireEvent.blur(textarea);

      // Wait for preview mode
      await waitFor(() => {
        expect(screen.getByTestId("sanitized-html")).toBeInTheDocument();
      });

      // Click on preview to switch back to edit mode
      fireEvent.click(screen.getByTestId("sanitized-html"));

      // Should be back in edit mode
      await waitFor(() => {
        expect(screen.getByTestId("modal-test-modal")).toBeInTheDocument();
      });
    });
  });

  describe("CSS class computation", () => {
    it("should use code-nohighlight class for short variable names", () => {
      render(<MustachePromptModal {...defaultProps} value="{{a}} {{b}}" />);
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      // Blur to preview mode
      const textarea = screen.getByTestId("modal-test-modal");
      fireEvent.blur(textarea);

      // The SanitizedHTMLWrapper should have code-nohighlight class
      const preview = screen.getByTestId("sanitized-html");
      expect(preview.className).toContain("code-nohighlight");
    });
  });

  describe("badge truncation", () => {
    it("should truncate long variable names in badges", () => {
      const longVarName = "a".repeat(70); // Over 59 characters
      render(
        <MustachePromptModal {...defaultProps} value={`{{${longVarName}}}`} />,
      );
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      // Should show truncated name with ...
      const badge = screen.getByText(/\.\.\.$/);
      expect(badge).toBeInTheDocument();
    });
  });

  describe("value synchronization", () => {
    it("should sync inputValue when value prop changes", () => {
      const { rerender } = render(
        <MustachePromptModal {...defaultProps} value="initial" />,
      );
      fireEvent.click(screen.getByTestId("mock-open-modal"));

      const textarea = screen.getByTestId("modal-test-modal");
      expect(textarea).toHaveValue("initial");

      // Update the value prop
      rerender(<MustachePromptModal {...defaultProps} value="updated" />);

      expect(textarea).toHaveValue("updated");
    });
  });
});
