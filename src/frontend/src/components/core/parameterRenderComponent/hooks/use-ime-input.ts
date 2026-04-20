import { useEffect, useRef, useState } from "react";

type InputLikeElement = HTMLInputElement | HTMLTextAreaElement;

interface UseIMEInputArgs<T extends InputLikeElement> {
  /** Parent-owned value. */
  value: string | undefined | null;
  /** Called once per committed change (per keystroke when idle; once on compositionend). */
  onCommit: (value: string) => void;
  /** Ref to the underlying input/textarea for cursor restoration. */
  inputRef: React.RefObject<T | null>;
  /** Current cursor position state (caller-owned so it can be referenced elsewhere). */
  cursor: number | null;
  /** Setter for cursor state. */
  setCursor: (cursor: number | null) => void;
}

interface IMEInputProps<T extends InputLikeElement> {
  value: string;
  onChange: (event: React.ChangeEvent<T>) => void;
  onCompositionStart: () => void;
  onCompositionEnd: (event: React.CompositionEvent<T>) => void;
}

interface UseIMEInputResult<T extends InputLikeElement> {
  /** Value to bind to the underlying input element's `value` prop. */
  displayValue: string;
  /** Pre-wired props to spread onto the underlying input element. */
  inputProps: IMEInputProps<T>;
}

/**
 * Shared IME-aware input adapter.
 *
 * The langflow node store update cascade takes 100-200ms per keystroke. When a
 * browser IME (macOS option-keys, Linux dead-keys, CJK composition) is active,
 * that much JS blocking on the main thread + any `setSelectionRange` call
 * causes the browser to silently abort composition, so dead-key accents like
 * `á` land as `´a`.
 *
 * This hook isolates the fix:
 * - Keeps a local `displayValue` so React's controlled `value` prop always
 *   matches the DOM, preventing reconciliation from aborting composition.
 * - Defers the expensive `onCommit` call until `compositionend`.
 * - Normalizes the composed string to NFC so consumers get canonical chars.
 * - Guards the caller's cursor-restore `useEffect` via `isComposingRef`.
 */
export function useIMEInput<T extends InputLikeElement>({
  value,
  onCommit,
  inputRef,
  cursor,
  setCursor,
}: UseIMEInputArgs<T>): UseIMEInputResult<T> {
  const isComposingRef = useRef(false);
  const [displayValue, setDisplayValue] = useState<string>(value ?? "");

  // Sync the local mirror with parent `value` when not composing. During
  // composition, the browser's IME owns the DOM; clobbering displayValue would
  // cancel the composition buffer.
  useEffect(() => {
    if (!isComposingRef.current) {
      setDisplayValue(value ?? "");
    }
  }, [value]);

  // Guarded cursor restore. Runs after displayValue changes so we follow the
  // visible text, not the parent store (which lags during composition).
  useEffect(() => {
    if (isComposingRef.current) return;
    if (cursor !== null && inputRef.current) {
      inputRef.current.setSelectionRange(cursor, cursor);
    }
  }, [cursor, displayValue, inputRef]);

  const handleChange = (event: React.ChangeEvent<T>) => {
    const nextValue = event.target.value;
    setDisplayValue(nextValue);

    const native = event.nativeEvent as InputEvent;
    if (isComposingRef.current || native.isComposing) return;

    setCursor(event.target.selectionStart);
    onCommit(nextValue);
  };

  const handleCompositionStart = () => {
    isComposingRef.current = true;
  };

  const handleCompositionEnd = (event: React.CompositionEvent<T>) => {
    isComposingRef.current = false;
    const composed = normalizeNFC(event.currentTarget.value);
    setDisplayValue(composed);
    setCursor(event.currentTarget.selectionStart);
    onCommit(composed);
  };

  return {
    displayValue,
    inputProps: {
      value: displayValue,
      onChange: handleChange,
      onCompositionStart: handleCompositionStart,
      onCompositionEnd: handleCompositionEnd,
    },
  };
}

function normalizeNFC(value: string | null | undefined): string {
  if (value == null) return "";
  return typeof value.normalize === "function" ? value.normalize("NFC") : value;
}
