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

type AgGridAccessibilityLabels = {
  endFocusBoundary: string;
  rows: string;
  startFocusBoundary: string;
  table: string;
};

function patchGridAccessibility(
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
      if (
        button.classList.contains("ag-disabled") ||
        button.getAttribute("aria-disabled") === "true"
      ) {
        setAttributeIfChanged(button, "aria-disabled", "true");
        setAttributeIfChanged(button, "tabindex", "-1");
        return;
      }

      setAttributeIfChanged(button, "tabindex", "0");
    });

  treeGrid?.querySelectorAll<HTMLElement>('[role="row"]').forEach((row) => {
    setAttributeIfChanged(row, "tabindex", "-1");

    if (row.closest('[aria-hidden="true"], .ag-hidden')) {
      row
        .querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        )
        .forEach((focusable) => {
          setAttributeIfChanged(focusable, "tabindex", "-1");
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
