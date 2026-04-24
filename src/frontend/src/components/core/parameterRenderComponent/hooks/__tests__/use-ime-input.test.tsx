import { act, fireEvent, render, screen } from "@testing-library/react";
import { useRef, useState } from "react";
import {
  normalizeNFC,
  useIMEInput,
  useIMEInputForOnChange,
} from "../use-ime-input";

interface HarnessProps {
  value: string | null | undefined;
  onCommit: jest.Mock<void, [string]>;
  initialCursor?: number | null;
}

const Harness = ({ value, onCommit, initialCursor = null }: HarnessProps) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [cursor, setCursor] = useState<number | null>(initialCursor);
  const { inputProps } = useIMEInput<HTMLInputElement>({
    value,
    onCommit,
    inputRef,
    cursor,
    setCursor,
  });

  return <input data-testid="ime-input" ref={inputRef} {...inputProps} />;
};

const BlurHarness = ({ value, onCommit }: HarnessProps) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [cursor, setCursor] = useState<number | null>(null);
  const { inputProps, flushPendingComposition } = useIMEInput<HTMLInputElement>(
    {
      value,
      onCommit,
      inputRef,
      cursor,
      setCursor,
    },
  );

  return (
    <input
      data-testid="ime-input"
      ref={inputRef}
      {...inputProps}
      onBlur={() => flushPendingComposition()}
    />
  );
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

  it("treats null value prop as empty string", () => {
    const onCommit = jest.fn();
    render(<Harness value={null} onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;
    expect(input.value).toBe("");
  });

  it("treats undefined value prop as empty string", () => {
    const onCommit = jest.fn();
    render(<Harness value={undefined} onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;
    expect(input.value).toBe("");
  });

  it("stays in composition mode on orphan compositionstart without compositionend", () => {
    const onCommit = jest.fn();
    render(<Harness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: "´" } });
    // No compositionend — simulates blur-mid-composition on Safari / abandoned IME.
    fireEvent.change(input, { target: { value: "´a" } });

    // Per hook contract: onCommit stays suppressed until the browser closes
    // the composition. The caller's blur handler is responsible for flushing.
    expect(onCommit).not.toHaveBeenCalled();
    expect(input.value).toBe("´a");
  });

  it("handles multiple compositionstart events without intervening compositionend", () => {
    const onCommit = jest.fn();
    render(<Harness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: "´" } });
    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: "´a" } });

    // Still composing — commit suppressed.
    expect(onCommit).not.toHaveBeenCalled();

    // When the browser finally ends the composition, one commit fires.
    input.value = "á";
    fireEvent.compositionEnd(input, { data: "á" });
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith("á");
  });

  it("handles null selectionStart on compositionend without throwing", () => {
    const onCommit = jest.fn();
    render(<Harness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    // selectionStart is null for some input types (email/number). Force it.
    Object.defineProperty(input, "selectionStart", {
      configurable: true,
      get: () => null,
    });
    input.value = "á";

    expect(() => fireEvent.compositionEnd(input, { data: "á" })).not.toThrow();
    expect(onCommit).toHaveBeenCalledWith("á");
  });

  it("does not re-fire onCommit when parent rerenders during composition", () => {
    const onCommit = jest.fn();
    const { rerender } = render(<Harness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: "´" } });

    rerender(<Harness value="stale" onCommit={onCommit} />);
    rerender(<Harness value="also-stale" onCommit={onCommit} />);

    expect(onCommit).not.toHaveBeenCalled();
  });
});

describe("useIMEInput flushPendingComposition", () => {
  it("commits NFC-normalized value on blur-mid-composition", () => {
    const onCommit = jest.fn();
    render(<BlurHarness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: "´" } });
    // Decomposed composed buffer still sitting in the DOM at blur time.
    input.value = "á";
    fireEvent.blur(input);

    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith("á");
  });

  it("resets composing state so later plain typing commits normally", () => {
    const onCommit = jest.fn();
    render(<BlurHarness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    input.value = "é";
    fireEvent.blur(input);
    expect(onCommit).toHaveBeenCalledTimes(1);

    // Focus returns, plain keystrokes must now commit — not get stuck.
    fireEvent.change(input, { target: { value: "éx" } });
    expect(onCommit).toHaveBeenCalledTimes(2);
    expect(onCommit).toHaveBeenNthCalledWith(2, "éx");
  });

  it("is a no-op when not composing", () => {
    const onCommit = jest.fn();
    render(<BlurHarness value="hello" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.blur(input);
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("does not double-commit when compositionend precedes blur", () => {
    const onCommit = jest.fn();
    render(<BlurHarness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    input.value = "á";
    fireEvent.compositionEnd(input, { data: "á" });
    fireEvent.blur(input);

    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith("á");
  });

  it("skips phantom commit when orphan blur leaves value unchanged from compositionStart", () => {
    const onCommit = jest.fn();
    render(<BlurHarness value="abc" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    // Dead-key only: user pressed Option+E then immediately blurred. No
    // composition progress committed to element.value.
    input.value = "abc";
    fireEvent.compositionStart(input);
    fireEvent.blur(input);

    expect(onCommit).not.toHaveBeenCalled();
  });
});

describe("useIMEInput unmount cleanup", () => {
  it("commits buffered composition value when input unmounts mid-composition", () => {
    const onCommit = jest.fn();
    const { unmount } = render(<Harness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: "é" } });
    expect(onCommit).not.toHaveBeenCalled();

    // Popover closes / modal dismisses — element gone before compositionend.
    unmount();

    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith("é");
  });

  it("does not commit on unmount when not composing", () => {
    const onCommit = jest.fn();
    const { unmount } = render(<Harness value="hello" onCommit={onCommit} />);

    unmount();
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("does not commit on unmount when composition made no progress", () => {
    const onCommit = jest.fn();
    const { unmount } = render(<Harness value="abc" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    input.value = "abc";
    fireEvent.compositionStart(input);
    unmount();

    expect(onCommit).not.toHaveBeenCalled();
  });
});

interface CancelHarnessProps extends HarnessProps {
  cancel?: boolean;
}

const CancelHarness = ({
  value,
  onCommit,
  cancel = false,
}: CancelHarnessProps) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [cursor, setCursor] = useState<number | null>(null);
  const { inputProps, cancelComposition } = useIMEInput<HTMLInputElement>({
    value,
    onCommit,
    inputRef,
    cursor,
    setCursor,
  });
  if (cancel) cancelComposition();
  return <input data-testid="ime-input" ref={inputRef} {...inputProps} />;
};

describe("useIMEInput cancelComposition", () => {
  it("clears composing flag without committing", () => {
    const onCommit = jest.fn();
    const { rerender } = render(<CancelHarness value="" onCommit={onCommit} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;

    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: "é" } });
    expect(onCommit).not.toHaveBeenCalled();

    // Caller invokes cancelComposition (e.g. selection-mode toggle).
    rerender(<CancelHarness value="" onCommit={onCommit} cancel />);

    // Plain typing after cancel must commit normally.
    fireEvent.change(input, { target: { value: "hi" } });
    expect(onCommit).toHaveBeenCalledTimes(1);
    expect(onCommit).toHaveBeenCalledWith("hi");
  });
});

describe("useIMEInputForOnChange", () => {
  it("keeps stable cancelComposition identity across onChange prop churn", () => {
    const cancelIdentities: unknown[] = [];
    const Capture = ({ counter }: { counter: number }) => {
      const inputRef = useRef<HTMLInputElement>(null);
      // Fresh onChange every render — would normally churn commitValue and
      // every callback derived from it.
      const onChange = (next: string) => void next;
      const { inputProps, cancelComposition } =
        useIMEInputForOnChange<HTMLInputElement>({
          value: String(counter),
          onChange,
          inputRef,
        });
      cancelIdentities.push(cancelComposition);
      return <input data-testid="ime-input" ref={inputRef} {...inputProps} />;
    };

    const { rerender } = render(<Capture counter={0} />);
    rerender(<Capture counter={1} />);
    rerender(<Capture counter={2} />);

    // All renders must see the same cancelComposition reference. If churn
    // returns, popoverObject's useEffect would re-fire on every parent render
    // and reset composition state under the user's fingers.
    expect(new Set(cancelIdentities).size).toBe(1);
  });

  it("uses the latest onChange via the internal ref", () => {
    const first = jest.fn();
    const second = jest.fn();
    const Capture = ({ onChange }: { onChange: (v: string) => void }) => {
      const inputRef = useRef<HTMLInputElement>(null);
      const { inputProps } = useIMEInputForOnChange<HTMLInputElement>({
        value: "",
        onChange,
        inputRef,
      });
      return <input data-testid="ime-input" ref={inputRef} {...inputProps} />;
    };

    const { rerender } = render(<Capture onChange={first} />);
    rerender(<Capture onChange={second} />);
    const input = screen.getByTestId("ime-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "x" } });

    // Latest onChange wins even though commitValue identity is frozen.
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledWith("x");
  });
});

describe("normalizeNFC", () => {
  it("returns empty string for null", () => {
    expect(normalizeNFC(null)).toBe("");
  });

  it("returns empty string for undefined", () => {
    expect(normalizeNFC(undefined)).toBe("");
  });

  it("converts decomposed Unicode to precomposed NFC", () => {
    // "a" + combining acute → single precomposed "á" (U+00E1).
    expect(normalizeNFC("a\u0301")).toBe("\u00e1");
  });

  it("leaves already-composed strings unchanged", () => {
    expect(normalizeNFC("café")).toBe("café");
  });

  it("falls back to the raw value when String.prototype.normalize is missing", () => {
    // Simulate a legacy environment where `.normalize` is absent on the string.
    const raw = "a\u0301";
    const legacy = Object.assign(Object.create(null), {
      normalize: undefined,
      toString: () => raw,
      valueOf: () => raw,
    }) as unknown as string;
    // typeof check guards against non-function `normalize`; returns the input.
    expect(normalizeNFC(legacy)).toBe(legacy);
  });
});
