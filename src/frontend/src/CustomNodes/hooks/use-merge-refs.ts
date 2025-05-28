import { MutableRefObject, useEffect, useRef } from "react";

type Ref<T> = MutableRefObject<T | null> | ((instance: T | null) => void);

export function isRefCallback<T>(
  ref: Ref<T>,
): ref is (instance: T | null) => void {
  return typeof ref === "function";
}

export function isRefObject<T>(ref: Ref<T>): ref is MutableRefObject<T> {
  return !isRefCallback(ref);
}

function useMergeRefs<T>(
  ...refs: (Ref<T> | null | undefined)[]
): Ref<T | null> {
  const targetRef: Ref<T | null> = useRef<T | null>(null);

  useEffect(() => {
    refs.forEach((ref) => {
      if (!ref) return;

      if (typeof ref === "function") {
        ref(targetRef.current);
      } else {
        ref.current = targetRef.current as T;
      }
    });
  }, [refs]);

  return targetRef;
}

export default useMergeRefs;
