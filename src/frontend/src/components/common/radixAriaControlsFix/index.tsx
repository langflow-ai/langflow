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

      // cmdk renders its option list as role="listbox" with role="option"
      // children that carry no tabindex. When the Command has a search input
      // (cmdk-input), focus stays on the input and aria-activedescendant marks
      // the active option — a pattern the checker accepts. But the model and
      // db-provider dropdowns use cmdk WITHOUT an input, so the listbox has no
      // tabbable descendant and the checker flags aria_child_tabbable. For those
      // input-less lists only, make the first enabled option tabbable so the
      // listbox is keyboard-reachable.
      //
      // The same input-less roots also get a visually-hidden <label
      // cmdk-label htmlFor={inputId}> from cmdk. With no CommandInput, that
      // for= target does not exist (label_ref_valid). Strip htmlFor only in
      // that case; searchable Commands keep the association to their input.
      document.querySelectorAll("[cmdk-list]").forEach((list) => {
        const root = list.closest("[cmdk-root]");
        if (root?.querySelector("[cmdk-input]")) return;

        root
          ?.querySelectorAll<HTMLLabelElement>("label[cmdk-label][for]")
          .forEach((label) => {
            label.removeAttribute("for");
          });

        const options = Array.from(
          list.querySelectorAll<HTMLElement>(
            '[role="option"]:not([aria-disabled="true"])',
          ),
        );
        if (options.length === 0) return;
        if (options.some((option) => option.getAttribute("tabindex") === "0")) {
          return;
        }
        options[0].setAttribute("tabindex", "0");
      });
    };

    fixClosedTriggers();

    const observer = new MutationObserver(fixClosedTriggers);
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["data-state", "aria-controls", "for"],
    });

    return () => observer.disconnect();
  }, []);

  return null;
}

export default RadixAriaControlsFix;
