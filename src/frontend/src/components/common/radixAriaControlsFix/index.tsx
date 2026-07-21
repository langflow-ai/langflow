import { useEffect } from "react";
import { useInertForAriaHiddenElements } from "@/components/ui/use-inert-for-aria-hidden";

const CONTROLS_CACHE_ATTR = "data-radix-aria-controls-cache";

export function RadixAriaControlsFix() {
  useInertForAriaHiddenElements();

  useEffect(() => {
    let isApplying = false;
    let frameId: number | null = null;

    const fixClosedTriggers = () => {
      isApplying = true;
      try {
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

        document
          .querySelectorAll("[data-radix-focus-guard]")
          .forEach((node) => {
            if (node.getAttribute("tabindex") !== "-1") {
              node.setAttribute("tabindex", "-1");
            }
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

          options.forEach((option) => {
            option.setAttribute("tabindex", "-1");
          });

          const preferred =
            options.find(
              (option) =>
                option.getAttribute("aria-selected") === "true" ||
                option.getAttribute("data-selected") === "true" ||
                option.hasAttribute("data-active"),
            ) ?? options[0];
          preferred.setAttribute("tabindex", "0");
        });
      } finally {
        isApplying = false;
      }
    };

    const scheduleFix = () => {
      if (isApplying) return;
      if (frameId !== null) return;
      frameId = requestAnimationFrame(() => {
        frameId = null;
        fixClosedTriggers();
      });
    };

    fixClosedTriggers();

    const observer = new MutationObserver(scheduleFix);
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["data-state"],
    });

    return () => {
      if (frameId !== null) cancelAnimationFrame(frameId);
      observer.disconnect();
    };
  }, []);

  return null;
}

export default RadixAriaControlsFix;
