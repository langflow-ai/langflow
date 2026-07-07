import { useCallback, useEffect, useRef } from "react";

function setAttributeIfChanged(
  element: HTMLElement | Element,
  name: string,
  value: string,
) {
  if (element.getAttribute(name) !== value) {
    element.setAttribute(name, value);
  }
}

export type AgGridAccessibilityLabels = {
  endFocusBoundary: string;
  rows: string;
  startFocusBoundary: string;
  table: string;
};

export function patchGridAccessibility(
  container: HTMLDivElement,
  labels: AgGridAccessibilityLabels,
) {
  const treeGrid = container.querySelector('[role="treegrid"]');
  if (treeGrid) {
    setAttributeIfChanged(treeGrid, "aria-label", labels.table);
    setAttributeIfChanged(treeGrid, "tabindex", "0");
  }

  container
    .querySelectorAll<HTMLElement>(".ag-tab-guard")
    .forEach((tabGuard, index) => {
      setAttributeIfChanged(tabGuard, "role", "button");
      setAttributeIfChanged(
        tabGuard,
        "aria-label",
        index === 0 ? labels.startFocusBoundary : labels.endFocusBoundary,
      );
    });

  container
    .querySelectorAll<HTMLElement>(
      '[role="rowgroup"], [data-langflow-a11y-rowgroup="true"]',
    )
    .forEach((rowGroup) => {
      const isHidden =
        rowGroup.getAttribute("aria-hidden") === "true" ||
        rowGroup.classList.contains("ag-hidden");
      const cells = Array.from(
        rowGroup.querySelectorAll<HTMLElement>(
          '[role="gridcell"], [role="columnheader"]',
        ),
      );
      const rows = Array.from(
        rowGroup.querySelectorAll<HTMLElement>('[role="row"]'),
      );

      if (isHidden || rows.length === 0) {
        setAttributeIfChanged(rowGroup, "role", "presentation");
        setAttributeIfChanged(rowGroup, "data-langflow-a11y-rowgroup", "true");
        rowGroup.removeAttribute("aria-label");
        rowGroup.removeAttribute("tabindex");
        return;
      }

      setAttributeIfChanged(rowGroup, "role", "rowgroup");
      setAttributeIfChanged(rowGroup, "data-langflow-a11y-rowgroup", "true");
      setAttributeIfChanged(rowGroup, "aria-label", labels.rows);

      rows.forEach((row) => {
        setAttributeIfChanged(row, "tabindex", "-1");
      });
      cells.forEach((cell) => {
        setAttributeIfChanged(cell, "tabindex", "-1");
      });
    });

  container
    .querySelectorAll<HTMLElement>(".ag-paging-button")
    .forEach((button) => {
      // Only use the class as input signal to avoid self-latching
      const isDisabled = button.classList.contains("ag-disabled");
      setAttributeIfChanged(
        button,
        "aria-disabled",
        isDisabled ? "true" : "false",
      );
      setAttributeIfChanged(button, "tabindex", isDisabled ? "-1" : "0");
    });

  treeGrid?.querySelectorAll<HTMLElement>('[role="row"]').forEach((row) => {
    setAttributeIfChanged(row, "tabindex", "-1");

    const isHidden = !!row.closest('[aria-hidden="true"], .ag-hidden');
    const focusableSelector =
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

    if (isHidden) {
      // Mark and demote focusable elements in hidden rows
      row.querySelectorAll<HTMLElement>(focusableSelector).forEach((el) => {
        if (!el.hasAttribute("data-langflow-a11y-demoted")) {
          el.setAttribute(
            "data-langflow-a11y-demoted",
            el.getAttribute("tabindex") ?? "",
          );
        }
        setAttributeIfChanged(el, "tabindex", "-1");
      });
    } else {
      // Restore previously demoted elements in visible rows
      row
        .querySelectorAll<HTMLElement>("[data-langflow-a11y-demoted]")
        .forEach((el) => {
          const original = el.getAttribute("data-langflow-a11y-demoted");
          if (original) {
            el.setAttribute("tabindex", original);
          } else {
            el.removeAttribute("tabindex");
          }
          el.removeAttribute("data-langflow-a11y-demoted");
        });
    }
  });
}

export function useAgGridAccessibilityPatch(labels: AgGridAccessibilityLabels) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const frameRef = useRef<number | undefined>(undefined);
  const timeoutRefs = useRef<number[]>([]);

  const clearScheduledPatch = useCallback(() => {
    if (frameRef.current !== undefined) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = undefined;
    }
    timeoutRefs.current.forEach(clearTimeout);
    timeoutRefs.current = [];
  }, []);

  const applyPatch = useCallback(() => {
    if (containerRef.current) {
      patchGridAccessibility(containerRef.current, labels);
    }
  }, [labels]);

  const schedulePatch = useCallback(() => {
    clearScheduledPatch();

    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = undefined;
      applyPatch();
    });
    timeoutRefs.current = [0, 100, 500, 1000].map((delay) =>
      window.setTimeout(applyPatch, delay),
    );
  }, [applyPatch, clearScheduledPatch]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new MutationObserver(schedulePatch);
    observer.observe(container, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["aria-hidden", "class", "role", "tabindex"],
    });
    schedulePatch();

    return () => {
      observer.disconnect();
      clearScheduledPatch();
    };
  }, [clearScheduledPatch, schedulePatch]);

  return { containerRef, schedulePatch };
}
