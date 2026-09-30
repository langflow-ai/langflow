import { render, screen } from "@testing-library/react";
import type { InputProps, PromptAreaComponentType } from "../../../types";
import PromptAreaComponent from "../index";

jest.mock("@/modals/promptModal", () => {
  return function MockPromptModal({ children }: { children: React.ReactNode }) {
    return <div data-testid="mock-prompt-modal">{children}</div>;
  };
});

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/components/common/sanitizedHTMLWrapper", () => {
  return function MockSanitizedHTMLWrapper({
    content,
    className,
  }: {
    content: string;
    className?: string;
  }) {
    return (
      <div
        data-testid="sanitized-html"
        className={className}
        dangerouslySetInnerHTML={{ __html: content }}
      />
    );
  };
});

describe("PromptAreaComponent variable highlighting", () => {
  const defaultProps = {
    field_name: "template",
    nodeClass: undefined,
    handleOnNewValue: jest.fn(),
    handleNodeClass: jest.fn(),
    value: "",
    disabled: false,
    editNode: false,
    id: "prompt-template",
    nodeId: "node-1",
    readonly: false,
  } as InputProps<string, PromptAreaComponentType>;

  it("marks a name starting with an underscore as invalid", () => {
    render(<PromptAreaComponent {...defaultProps} value="Hello {_x}!" />);

    expect(screen.getByTestId("sanitized-html").innerHTML).toContain(
      '<span class="chat-message-highlight-invalid">{_x}</span>',
    );
  });

  it("keeps a regular name highlighted normally", () => {
    render(<PromptAreaComponent {...defaultProps} value="Hello {var}!" />);

    expect(screen.getByTestId("sanitized-html").innerHTML).toContain(
      '<span class="chat-message-highlight">{var}</span>',
    );
  });

  it("keeps an underscore that is not the first character valid", () => {
    render(<PromptAreaComponent {...defaultProps} value="Hi {user_name}!" />);

    expect(screen.getByTestId("sanitized-html").innerHTML).toContain(
      '<span class="chat-message-highlight">{user_name}</span>',
    );
  });

  it("marks only the offending variable in a mixed template", () => {
    render(
      <PromptAreaComponent {...defaultProps} value="Hello {_x}, meet {var}." />,
    );

    const html = screen.getByTestId("sanitized-html").innerHTML;
    expect(html).toContain(
      '<span class="chat-message-highlight-invalid">{_x}</span>',
    );
    expect(html).toContain('<span class="chat-message-highlight">{var}</span>');
  });

  it.each(["1var", "my var", "code"])(
    "marks %s as invalid, the way Check & Save does",
    (name) => {
      render(
        <PromptAreaComponent {...defaultProps} value={`Hello {${name}}!`} />,
      );

      expect(screen.getByTestId("sanitized-html").innerHTML).toContain(
        `<span class="chat-message-highlight-invalid">{${name}}</span>`,
      );
    },
  );

  it("leaves a JSON literal highlighted normally", () => {
    // The backend reads the field name up to the `:`, so `{"a": 1}` is accepted.
    render(<PromptAreaComponent {...defaultProps} value={'Body {"a": 1}'} />);

    expect(screen.getByTestId("sanitized-html").innerHTML).not.toContain(
      "chat-message-highlight-invalid",
    );
  });

  it("leaves double-brace escapes untouched", () => {
    render(
      <PromptAreaComponent {...defaultProps} value="Literal {{_x}} here" />,
    );

    expect(screen.getByTestId("sanitized-html").innerHTML).not.toContain(
      "chat-message-highlight-invalid",
    );
  });
});
