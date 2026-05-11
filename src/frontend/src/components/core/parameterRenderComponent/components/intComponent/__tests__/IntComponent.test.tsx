import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import IntComponent from "../index";

type MockProps = {
  children?: ReactNode;
  onChange?: React.ChangeEventHandler<HTMLInputElement>;
  onKeyDown?: React.KeyboardEventHandler<HTMLInputElement>;
  onInput?: React.FormEventHandler<HTMLInputElement>;
  onMouseDown?: React.MouseEventHandler<HTMLButtonElement>;
  onClickCapture?: React.MouseEventHandler<HTMLButtonElement>;
  disabled?: boolean;
  [key: string]: unknown;
};

// Mock Chakra UI NumberInput as plain HTML equivalents
jest.mock("@chakra-ui/number-input", () => ({
  NumberInput: ({
    children,
    onChange: _onChange,
    isDisabled: _isDisabled,
    value: _value,
    ...props
  }: MockProps) => (
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
  NumberIncrementStepper: ({
    children,
    onClickCapture: _onClickCapture,
    ...props
  }: MockProps) => (
    <button
      type="button"
      {...(props as React.ButtonHTMLAttributes<HTMLButtonElement>)}
    >
      {children}
    </button>
  ),
  NumberDecrementStepper: ({
    children,
    onClickCapture,
    ...props
  }: MockProps) => (
    <button
      type="button"
      onMouseDown={onClickCapture as React.MouseEventHandler<HTMLButtonElement>}
      {...(props as React.ButtonHTMLAttributes<HTMLButtonElement>)}
    >
      {children}
    </button>
  ),
}));

jest.mock("lucide-react", () => ({
  MinusIcon: () => <span>-</span>,
  PlusIcon: () => <span>+</span>,
}));

jest.mock("@/constants/constants", () => ({ ICON_STROKE_WIDTH: 1.5 }));
jest.mock("@/utils/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));
jest.mock("@/utils/reactflowUtils", () => ({ handleKeyDown: jest.fn() }));

const defaultProps = {
  value: 100,
  handleOnNewValue: jest.fn(),
  rangeSpec: { min: 1, max: 131072, step: 1 },
  name: "max_tokens",
  disabled: false,
  editNode: false,
  id: "max-tokens-input",
};

describe("IntComponent – handleInputChange (clearing the field)", () => {
  beforeEach(() => jest.clearAllMocks());

  it("does NOT reset the input when the field is cleared (empty string)", () => {
    render(<IntComponent {...defaultProps} />);
    const input = screen.getByTestId("max-tokens-input") as HTMLInputElement;

    // Simulate the user clearing the field via Backspace/Delete
    Object.defineProperty(input, "value", { writable: true, value: "" });
    fireEvent.input(input);

    // The DOM value should remain "" — not snapped back to "1"
    expect(input.value).toBe("");
  });

  it("resets the input to min when value is below min (e.g. 0 for max_tokens)", () => {
    render(<IntComponent {...defaultProps} />);
    const input = screen.getByTestId("max-tokens-input") as HTMLInputElement;

    Object.defineProperty(input, "value", { writable: true, value: "0" });
    fireEvent.input(input);

    expect(input.value).toBe("1");
  });

  it("resets the input to min when a negative value is typed", () => {
    render(<IntComponent {...defaultProps} />);
    const input = screen.getByTestId("max-tokens-input") as HTMLInputElement;

    Object.defineProperty(input, "value", { writable: true, value: "-5" });
    fireEvent.input(input);

    expect(input.value).toBe("1");
  });

  it("does not reset the input when value is at or above min", () => {
    render(<IntComponent {...defaultProps} />);
    const input = screen.getByTestId("max-tokens-input") as HTMLInputElement;

    Object.defineProperty(input, "value", { writable: true, value: "50" });
    fireEvent.input(input);

    expect(input.value).toBe("50");
  });
});
