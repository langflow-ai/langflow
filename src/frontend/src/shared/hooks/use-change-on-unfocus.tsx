import { type RefObject, useEffect } from "react";

interface UseChangeOnUnfocusProps<T> {
  selected?: boolean;
  value: T;
  onChange?: (value: T) => void;
  defaultValue: T;
  shouldChangeValue?: (value: T) => boolean;
  nodeRef: RefObject<HTMLDivElement>;
  callback?: () => void;
  callbackEscape?: () => void;
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

    const handleVisibilityChange = () => {
      if (document.hidden && shouldChangeValue?.(value)) {
        onChange?.(defaultValue);
        callback?.();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
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
