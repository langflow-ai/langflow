import { useCallback, useEffect, useRef, useState } from "react";

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
  onCompositionStart: (event: React.CompositionEvent<T>) => void;
  onCompositionEnd: (event: React.CompositionEvent<T>) => void;
}

interface UseIMEInputResult<T extends InputLikeElement> {
  /** Value to bind to the underlying input element's `value` prop. */
  displayValue: string;
  /** Pre-wired props to spread onto the underlying input element. */
  inputProps: IMEInputProps<T>;
  /**
   * Commit any in-flight composition buffer. Call from `onBlur` so
   * blur-mid-composition (common on macOS dead keys / Safari) still fires
   * `onCommit` instead of silently dropping the composed text and stranding
   * the field in a stuck-composing state.
   */
  flushPendingComposition: () => void;
  /**
   * Drop any in-flight composition state without committing. Use when the
   * input is about to enter a non-text mode (e.g. selection-mode swap) where
   * `compositionend` will never fire and the stuck flag would otherwise block
   * later plain-typing commits.
   */
  cancelComposition: () => void;
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

  // Latest snapshot of the composition buffer + the value at compositionStart.
  // Used to recover the in-flight text if the input unmounts (popover close,
  // disabled flip) before `compositionend` or blur can fire.
  const lastCompositionValueRef = useRef<string | null>(null);
  const compositionStartValueRef = useRef<string | null>(null);

  // Latest onCommit captured for the unmount cleanup effect, which has empty
  // deps and would otherwise close over a stale callback.
  const onCommitRef = useRef(onCommit);
  useEffect(() => {
    onCommitRef.current = onCommit;
  }, [onCommit]);

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

  // Unmount-mid-composition rescue: commit the latest composition snapshot so
  // popover-close / modal-dismiss during dead-key entry doesn't drop input.
  useEffect(() => {
    return () => {
      if (!isComposingRef.current) return;
      const buffered = lastCompositionValueRef.current;
      const startValue = compositionStartValueRef.current;
      isComposingRef.current = false;
      lastCompositionValueRef.current = null;
      compositionStartValueRef.current = null;
      if (buffered === null || buffered === startValue) return;
      onCommitRef.current(normalizeNFC(buffered));
    };
  }, []);

  const handleChange = (event: React.ChangeEvent<T>) => {
    const nextValue = event.target.value;
    setDisplayValue(nextValue);

    const native = event.nativeEvent as InputEvent;
    if (isComposingRef.current || native.isComposing) {
      lastCompositionValueRef.current = nextValue;
      return;
    }

    setCursor(event.target.selectionStart);
    onCommit(nextValue);
  };

  const handleCompositionStart = (event: React.CompositionEvent<T>) => {
    isComposingRef.current = true;
    compositionStartValueRef.current = event.currentTarget.value;
    lastCompositionValueRef.current = event.currentTarget.value;
  };

  const handleCompositionEnd = (event: React.CompositionEvent<T>) => {
    isComposingRef.current = false;
    lastCompositionValueRef.current = null;
    compositionStartValueRef.current = null;
    const composed = normalizeNFC(event.currentTarget.value);
    setDisplayValue(composed);
    setCursor(event.currentTarget.selectionStart);
    onCommit(composed);
  };

  const flushPendingComposition = useCallback(() => {
    if (!isComposingRef.current) return;
    const element = inputRef.current;
    const startValue = compositionStartValueRef.current;
    isComposingRef.current = false;
    lastCompositionValueRef.current = null;
    compositionStartValueRef.current = null;
    if (!element) return;
    const rawValue = element.value;
    // Skip phantom commits: orphan dead-key (Option+E then blur) leaves the
    // element value identical to the pre-composition snapshot, so there is
    // nothing real to commit.
    if (rawValue === startValue) return;
    const nextValue = normalizeNFC(rawValue);
    setDisplayValue(nextValue);
    setCursor(element.selectionStart);
    onCommit(nextValue);
  }, [inputRef, onCommit, setCursor]);

  const cancelComposition = useCallback(() => {
    isComposingRef.current = false;
    lastCompositionValueRef.current = null;
    compositionStartValueRef.current = null;
  }, []);

  return {
    displayValue,
    inputProps: {
      value: displayValue,
      onChange: handleChange,
      onCompositionStart: handleCompositionStart,
      onCompositionEnd: handleCompositionEnd,
    },
    flushPendingComposition,
    cancelComposition,
  };
}

export function normalizeNFC(value: string | null | undefined): string {
  if (value == null) return "";
  return typeof value.normalize === "function" ? value.normalize("NFC") : value;
}

/**
 * Convenience wrapper for the common case: owner-component whose commit is a
 * plain `(value: string) => void` callback. Bundles cursor state + commitValue
 * memoization so call sites don't each roll their own.
 */
export function useIMEInputForOnChange<T extends InputLikeElement>({
  value,
  onChange,
  inputRef,
}: {
  value: string | null | undefined;
  onChange?: (value: string) => void;
  inputRef: React.RefObject<T | null>;
}): UseIMEInputResult<T> {
  const [cursor, setCursor] = useState<number | null>(null);
  // Stash onChange in a ref so commitValue identity stays stable across
  // renders. Without this, every parent rerender churns commitValue, which
  // churns flushPendingComposition + cancelComposition, defeating their
  // useCallback memoization and re-running any downstream effects keyed on
  // those identities.
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);
  const commitValue = useCallback(
    (newValue: string) => onChangeRef.current?.(newValue),
    [],
  );
  return useIMEInput<T>({
    value: value ?? "",
    onCommit: commitValue,
    inputRef,
    cursor,
    setCursor,
  });
}
