import { useEffect } from "react";

export function useOnClickOutside(ref, handler) {
  useEffect(() => {
    const listener = (event) => {
      // Do nothing if clicking ref's element or its children
      if (!ref.current || ref.current.contains(event.target)) {
        return;
      }

      handler(event);
    };

    // Attach the listener to the document
    document.addEventListener("mousedown", listener, { passive: true });

    // Attach the listener to the react-flow instance
    const reactFlowContainer = document.querySelector(".react-flow");
    if (reactFlowContainer) {
      reactFlowContainer.addEventListener("mousedown", listener, {
        passive: true,
      });
    }

    // Clean up the listener when the component is unmounted
    return () => {
      document.removeEventListener("mousedown", listener);
      if (reactFlowContainer) {
        reactFlowContainer.removeEventListener("mousedown", listener);
      }
    };
  }, [ref, handler]); // Rerun only if ref or handler changes
}
