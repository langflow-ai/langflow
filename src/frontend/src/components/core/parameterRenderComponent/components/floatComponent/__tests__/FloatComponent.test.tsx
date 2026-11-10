import { fireEvent, render, screen } from "@testing-library/react";
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
jest.mock("@chakra-ui/number-input", () => {
  const { createContext, useContext } = jest.requireActual("react");
  // Like Chakra, NumberInput owns the value and its field displays it.
  const ValueContext = createContext(undefined);
  return {
    // Chakra calls onChange with the value string, not a DOM event; drop it so the
    // field's own onChange drives the value, as it does in the real component.
    NumberInput: ({
      children,
      onChange: _onChange,
      value,
      ...props
    }: MockProps) => (
      <ValueContext.Provider value={value}>
        <div {...(props as Record<string, unknown>)}>{children}</div>
      </ValueContext.Provider>
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
        value={useContext(ValueContext)}
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
  };
});

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

describe("FloatComponent blank values", () => {
  beforeEach(() => jest.clearAllMocks());

  it("should_keep_a_cleared_field_blank_when_preserve_empty_is_set", () => {
    render(<FloatComponent {...defaultProps} value={0.7} preserveEmpty />);
    const input = screen.getByTestId("float-input");
    fireEvent.change(input, { target: { value: "0.5" } });
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.blur(input);
    expect(defaultProps.handleOnNewValue).toHaveBeenCalledWith({ value: "" });
  });

  it("should_render_an_unset_preserve_empty_value_as_blank", () => {
    render(<FloatComponent {...defaultProps} value={null} preserveEmpty />);
    expect(screen.getByTestId("float-input")).toHaveValue("");
  });

  it("should_render_a_zero_preserve_empty_value_as_zero", () => {
    render(<FloatComponent {...defaultProps} value={0} preserveEmpty />);
    expect(screen.getByTestId("float-input")).toHaveValue("0");
  });

  it("should_clear_a_disabled_preserve_empty_field_to_blank_not_zero", () => {
    render(
      <FloatComponent {...defaultProps} value={0.7} preserveEmpty disabled />,
    );
    expect(defaultProps.handleOnNewValue).toHaveBeenCalledWith(
      { value: "" },
      { skipSnapshot: true },
    );
    expect(defaultProps.handleOnNewValue).not.toHaveBeenCalledWith(
      { value: 0 },
      expect.anything(),
    );
  });

  it("should_leave_a_disabled_blank_preserve_empty_field_alone", () => {
    render(
      <FloatComponent {...defaultProps} value={null} preserveEmpty disabled />,
    );
    expect(defaultProps.handleOnNewValue).not.toHaveBeenCalled();
  });

  it("should_turn_a_cleared_field_into_zero_without_preserve_empty", () => {
    render(<FloatComponent {...defaultProps} value={0.7} />);
    const input = screen.getByTestId("float-input");
    fireEvent.change(input, { target: { value: "0.5" } });
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.blur(input);
    expect(defaultProps.handleOnNewValue).toHaveBeenCalledWith({ value: 0 });
  });
});
