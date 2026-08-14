import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { axe } from "@/utils/a11y-test";
import FloatComponent from "../index";

type MockProps = {
  children?: ReactNode;
  onChange?: React.ChangeEventHandler<HTMLInputElement>;
  onKeyDown?: React.KeyboardEventHandler<HTMLInputElement>;
  onInput?: React.FormEventHandler<HTMLInputElement>;
  disabled?: boolean;
  [key: string]: unknown;
};

// Mock Chakra UI NumberInput as plain HTML equivalents, matching the pattern
// used for IntComponent (Chakra swallows unrecognized/uncontrolled props).
jest.mock("@chakra-ui/number-input", () => ({
  NumberInput: ({ children, ...props }: MockProps) => (
    <div {...(props as Record<string, unknown>)}>{children}</div>
  ),
  NumberInputField: ({
    onChange,
    onKeyDown,
    onInput,
    disabled,
    children: _children,
    ...props
  }: MockProps) => (
    <input
      onChange={onChange}
      onKeyDown={onKeyDown}
      onInput={onInput}
      disabled={disabled}
      {...(props as React.InputHTMLAttributes<HTMLInputElement>)}
    />
  ),
  NumberInputStepper: ({ children }: MockProps) => <div>{children}</div>,
  NumberIncrementStepper: ({ children, ...props }: MockProps) => (
    <button type="button" {...(props as Record<string, unknown>)}>
      {children}
    </button>
  ),
  NumberDecrementStepper: ({ children, ...props }: MockProps) => (
    <button type="button" {...(props as Record<string, unknown>)}>
      {children}
    </button>
  ),
}));

jest.mock("lucide-react", () => ({
  MinusIcon: () => <span>-</span>,
  PlusIcon: () => <span>+</span>,
}));

const defaultProps = {
  value: 1.5,
  handleOnNewValue: jest.fn(),
  rangeSpec: { min: 0, max: 10, step: 0.1 },
  disabled: false,
  editNode: false,
  id: "float-input",
};

describe("FloatComponent accessibility", () => {
  beforeEach(() => jest.clearAllMocks());

  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="float-label">Temperature</span>
        <FloatComponent {...defaultProps} ariaLabelledBy="float-label" />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_the_forwarded_field_label_as_accessible_name", () => {
    render(
      <>
        <span id="float-label">Temperature</span>
        <FloatComponent {...defaultProps} ariaLabelledBy="float-label" />
      </>,
    );
    expect(
      screen.getByTestId("float-input").getAttribute("aria-labelledby"),
    ).toBe("float-label");
  });

  it("should_render_with_no_aria_labelledby_when_no_field_label_is_forwarded", () => {
    render(<FloatComponent {...defaultProps} />);
    expect(screen.getByTestId("float-input")).not.toHaveAttribute(
      "aria-labelledby",
    );
  });
});
