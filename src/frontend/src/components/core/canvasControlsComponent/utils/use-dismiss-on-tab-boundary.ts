import { type KeyboardEvent, useCallback, useRef } from "react";
import { tabbable } from "tabbable";

const getTabbableElements = (root: HTMLElement) =>
  tabbable(root, {
    displayCheck: process.env.NODE_ENV === "test" ? "none" : "full",
  }).filter(
    (element) =>
      !element.hasAttribute("data-radix-focus-guard") &&
      !element.closest("[inert]") &&
      !element.closest('[aria-hidden="true"]'),
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
      const isLeavingBackward =
        event.shiftKey && activeElement === firstContainerTabbable;
      const isLeavingForward =
        !event.shiftKey && activeElement === lastContainerTabbable;

      if (!isLeavingBackward && !isLeavingForward) return;

      const documentTabbables = getTabbableElements(document.body);
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
