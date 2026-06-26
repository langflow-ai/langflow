import { type KeyboardEvent, useCallback, useRef } from "react";

const TABBABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

const getTabbableElements = (root: ParentNode) =>
  Array.from(root.querySelectorAll<HTMLElement>(TABBABLE_SELECTOR)).filter(
    (element) =>
      element.tabIndex >= 0 &&
      element.getAttribute("aria-hidden") !== "true" &&
      !element.hasAttribute("data-radix-focus-guard"),
  );

export function useDismissOnTabBoundary<TElement extends HTMLElement>(
  onDismiss: () => void,
) {
  const containerRef = useRef<TElement>(null);

  const handleTabBoundary = useCallback(
    (event: KeyboardEvent<TElement>) => {
      if (event.key !== "Tab") return;

      const container = containerRef.current;
      const activeElement = document.activeElement as HTMLElement | null;
      if (!container || !activeElement || !container.contains(activeElement)) {
        return;
      }

      const containerTabbables = getTabbableElements(container);
      const firstContainerTabbable = containerTabbables[0];
      const lastContainerTabbable = containerTabbables.at(-1);
      const leavingBackward =
        event.shiftKey && activeElement === firstContainerTabbable;
      const leavingForward =
        !event.shiftKey && activeElement === lastContainerTabbable;

      if (!leavingBackward && !leavingForward) return;

      const documentTabbables = getTabbableElements(document);
      const activeIndex = documentTabbables.indexOf(activeElement);
      const candidates = event.shiftKey
        ? documentTabbables.slice(0, activeIndex).reverse()
        : documentTabbables.slice(activeIndex + 1);
      const nextFocusable = candidates.find(
        (element) => !container.contains(element),
      );

      event.preventDefault();
      onDismiss();
      nextFocusable?.focus();
    },
    [onDismiss],
  );

  return { containerRef, handleTabBoundary };
}
