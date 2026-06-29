import * as React from "react";

export function useClosedTriggerAriaControls<T extends HTMLElement>(
  forwardedRef: React.ForwardedRef<T>,
) {
  const triggerRef = React.useRef<T | null>(null);

  const setTriggerRef = React.useCallback(
    (node: T | null) => {
      triggerRef.current = node;

      if (typeof forwardedRef === "function") {
        forwardedRef(node);
      } else if (forwardedRef) {
        forwardedRef.current = node;
      }
    },
    [forwardedRef],
  );

  React.useEffect(() => {
    const trigger = triggerRef.current;
    if (!trigger) {
      return;
    }

    const removeControlsWhenClosed = () => {
      if (trigger.getAttribute("aria-expanded") === "false") {
        trigger.removeAttribute("aria-controls");
      }
    };

    removeControlsWhenClosed();

    const observer = new MutationObserver(removeControlsWhenClosed);
    observer.observe(trigger, {
      attributes: true,
      attributeFilter: ["aria-controls", "aria-expanded"],
    });

    return () => observer.disconnect();
  }, []);

  return setTriggerRef;
}
