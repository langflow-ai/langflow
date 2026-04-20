import { act, fireEvent, render, screen } from "@testing-library/react";
import { useRef, useState } from "react";
import { useIMEInput } from "../use-ime-input";

interface HarnessProps {
  value: string;
  onCommit: jest.Mock<void, [string]>;
}

const Harness = ({ value, onCommit }: HarnessProps) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [cursor, setCursor] = useState<number | null>(null);
  const { inputProps } = useIMEInput<HTMLInputElement>({
    value,
    onCommit,
    inputRef,
    cursor,
    setCursor,
  });

  return <input data-testid="ime-input" ref={inputRef} {...inputProps} />;
};

describe("useIMEInput", () => {
  it("fires onCommit per keystroke for plain typing", () => {
    const onCommit = jest.fn();
    render(<Harness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "h" } });
    fireEvent.change(input, { target: { value: "hi" } });

    expect(onCommit).toHaveBeenCalledTimes(2);
    expect(onCommit).toHaveBeenNthCalledWith(1, "h");
    expect(onCommit).toHaveBeenNthCalledWith(2, "hi");
  });

  it("skips onCommit during composition and fires once on compositionend with NFC", () => {
    const onCommit = jest.fn();
    render(<Harness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: "´" } });
    fireEvent.change(input, { target: { value: "á" } });
    expect(onCommit).not.toHaveBeenCalled();

    // Composed value arrives in decomposed form (e + combining acute). The
    // hook must normalize it to the precomposed canonical `á` (\u00e1).
    const decomposed = "a\u0301";
    input.value = decomposed;
    fireEvent.compositionEnd(input, { data: decomposed });

    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith("\u00e1");
  });

  it("updates displayValue during composition even though onCommit is skipped", () => {
    const onCommit = jest.fn();
    render(<Harness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: "´" } });

    // React reflects the local mirror as the controlled value.
    expect(input.value).toBe("´");
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("syncs displayValue when parent value changes while idle", () => {
    const onCommit = jest.fn();
    const { rerender } = render(<Harness value="old" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;
    expect(input.value).toBe("old");

    rerender(<Harness value="new" onCommit={onCommit} />);
    expect(input.value).toBe("new");
  });

  it("does not clobber displayValue when parent value changes mid-composition", () => {
    const onCommit = jest.fn();
    const { rerender } = render(<Harness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    act(() => {
      fireEvent.change(input, { target: { value: "´" } });
    });
    expect(input.value).toBe("´");

    // Parent value changes to something else during composition (e.g. another
    // actor updating the store). The local display must keep what the user
    // is actively composing.
    rerender(<Harness value="stale" onCommit={onCommit} />);
    expect(input.value).toBe("´");
  });

  it("suppresses onCommit when nativeEvent.isComposing is true even without compositionstart", () => {
    const onCommit = jest.fn();
    render(<Harness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    const native = new InputEvent("input", { isComposing: true, data: "á" });
    Object.defineProperty(native, "target", { value: input });
    input.value = "á";
    fireEvent(input, native);

    expect(onCommit).not.toHaveBeenCalled();
  });
});
