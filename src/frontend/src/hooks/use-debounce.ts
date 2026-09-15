import { debounce } from "lodash";
import { useLayoutEffect, useMemo, useRef } from "react";

type DebounceOptions = {
  /**
   * Longest a call may be deferred while events keep arriving.
   *
   * Without it a trailing debounce has no ceiling: someone who keeps editing
   * never triggers the callback at all, so an autosave can hold an entire
   * session in memory. Opt in per caller -- most debounces here want the plain
   * trailing behaviour.
   */
  maxWait?: number;
};

export function useDebounce<TArgs extends unknown[]>(
  callback: (...args: TArgs) => unknown,
  delay: number,
  options?: DebounceOptions,
) {
  const callbackRef = useRef(callback);
  useLayoutEffect(() => {
    callbackRef.current = callback;
  });
  const maxWait = options?.maxWait;
  return useMemo(
    () =>
      debounce(
        (...args: TArgs) => callbackRef.current(...args),
        delay,
        maxWait === undefined ? undefined : { maxWait },
      ),
    [delay, maxWait],
  );
}
