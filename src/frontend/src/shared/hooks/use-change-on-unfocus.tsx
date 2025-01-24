import { RefObject, useEffect } from "react";

interface UseChangeOnUnfocusProps<T> {
  selected?: boolean;
  value: T;
  onChange?: (value: T) => void;
  defaultValue: T;
  shouldChangeValue?: (value: T) => boolean;
  nodeRef: RefObject<HTMLDivElement>;
  callback?: () => void;
}

export function useChangeOnUnfocus<T>({
  selected,
  value,
  onChange,
  defaultValue,
  shouldChangeValue,
  nodeRef,
  callback,
}: UseChangeOnUnfocusProps<T>) {
  useEffect(() => {
    if (!selected) {
      onChange?.(defaultValue);
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && shouldChangeValue?.(value)) {
        onChange?.(defaultValue);
        callback?.();
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden && shouldChangeValue?.(value)) {
        onChange?.(defaultValue);
        callback?.();
      }
    };

    const handleBlur = (event: FocusEvent) => {
      if (
        shouldChangeValue?.(value) &&
        nodeRef.current &&
        !nodeRef.current.contains(event.relatedTarget as Node)
      ) {
        onChange?.(defaultValue);
        callback?.();
      }
    };

    document.addEventListener("keydown", handleEscape);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    const node = nodeRef.current;
    if (node) {
      node.addEventListener("focusout", handleBlur);
    }

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      if (node) {
        node.removeEventListener("focusout", handleBlur);
      }
    };
  }, [
    selected,
    value,
    onChange,
    defaultValue,
    shouldChangeValue,
    nodeRef,
    callback,
  ]);
}
