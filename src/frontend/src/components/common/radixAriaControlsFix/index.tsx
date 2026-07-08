import { useEffect } from "react";
import { useInertForAriaHiddenElements } from "@/components/ui/use-inert-for-aria-hidden";

const CONTROLS_CACHE_ATTR = "data-radix-aria-controls-cache";

export function RadixAriaControlsFix() {
  useInertForAriaHiddenElements();

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
