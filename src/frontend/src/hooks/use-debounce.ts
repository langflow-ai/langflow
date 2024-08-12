import { debounce } from "lodash";
import { useLayoutEffect, useMemo, useRef } from "react";

export function useDebounce(callback, delay) {
  const callbackRef = useRef(callback);
  useLayoutEffect(() => {
    callbackRef.current = callback;
  });
  return useMemo(
    () => debounce((...args) => callbackRef.current(...args), delay),
    [delay],
  );
}
