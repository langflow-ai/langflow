import * as React from "react";

export function useClosedTriggerAriaControls<T extends HTMLElement>(
  forwardedRef: React.ForwardedRef<T>,
) {
  const [trigger, setTrigger] = React.useState<T | null>(null);
  const savedControlsRef = React.useRef<string | null>(null);

  const setTriggerRef = React.useCallback(
    (node: T | null) => {
      setTrigger((current) => (current === node ? current : node));

      if (typeof forwardedRef === "function") {
        forwardedRef(node);
      } else if (forwardedRef) {
        forwardedRef.current = node;
      }
    },
    [forwardedRef],
  );

  React.useEffect(() => {
    if (!trigger) {
      return;
    }

    const syncControls = () => {
      const expanded = trigger.getAttribute("aria-expanded");
      const controls = trigger.getAttribute("aria-controls");

      if (controls) {
        savedControlsRef.current = controls;
      }

      if (expanded === "false") {
        trigger.removeAttribute("aria-controls");
      } else if (
        expanded === "true" &&
        savedControlsRef.current &&
        !trigger.hasAttribute("aria-controls")
      ) {
        trigger.setAttribute("aria-controls", savedControlsRef.current);
      }
    };

    syncControls();

    const observer = new MutationObserver(syncControls);
    observer.observe(trigger, {
      attributes: true,
      attributeFilter: ["aria-controls", "aria-expanded"],
    });

    return () => observer.disconnect();
  }, [trigger]);

  return setTriggerRef;
}
