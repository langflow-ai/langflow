import { useEffect } from "react";

const CONTROLS_CACHE_ATTR = "data-radix-aria-controls-cache";

/**
 * Radix sets aria-controls on closed popovers/selects/dialogs while the
 * referenced node is aria-hidden or unmounted. IBM's checker treats that as
 * aria_id_unique violation. Strip the attribute whenever the trigger is closed.
 *
 * The stripped value is cached on the node first: since the id Radix passes
 * in is stable across renders, React's reconciler sees an "unchanged" prop
 * on the next render and won't re-apply it once we've removed it from the
 * DOM directly, so a trigger that closes and later reopens would otherwise
 * be left with no aria-controls at all. Restoring from the cache when the
 * trigger re-opens keeps that reference intact.
 */
export function RadixAriaControlsFix() {
  useEffect(() => {
    const fixClosedTriggers = () => {
      document
        .querySelectorAll('[data-state="closed"][aria-controls]')
        .forEach((node) => {
          const controls = node.getAttribute("aria-controls");
          if (controls) node.setAttribute(CONTROLS_CACHE_ATTR, controls);
          node.removeAttribute("aria-controls");
        });

      document
        .querySelectorAll(
          `[data-state="open"][${CONTROLS_CACHE_ATTR}]:not([aria-controls])`,
        )
        .forEach((node) => {
          const cached = node.getAttribute(CONTROLS_CACHE_ATTR);
          if (cached) node.setAttribute("aria-controls", cached);
        });

      document.querySelectorAll("[data-radix-focus-guard]").forEach((node) => {
        node.setAttribute("tabindex", "-1");
        node.setAttribute("aria-hidden", "true");
      });
    };

    fixClosedTriggers();

    const observer = new MutationObserver(fixClosedTriggers);
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["data-state", "aria-controls"],
    });

    return () => observer.disconnect();
  }, []);

  return null;
}

export default RadixAriaControlsFix;
