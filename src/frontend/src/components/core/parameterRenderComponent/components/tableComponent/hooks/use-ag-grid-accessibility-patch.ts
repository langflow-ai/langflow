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

function patchGridAccessibility(container: HTMLDivElement, tableLabel: string) {
  const treeGrid = container.querySelector('[role="treegrid"]');
  if (treeGrid) {
    setAttributeIfChanged(treeGrid, "aria-label", tableLabel);
  }

  container
    .querySelectorAll<HTMLElement>(".ag-tab-guard")
    .forEach((tabGuard, index) => {
      setAttributeIfChanged(tabGuard, "role", "button");
      setAttributeIfChanged(
        tabGuard,
        "aria-label",
        index === 0
          ? `${tableLabel} start focus boundary`
          : `${tableLabel} end focus boundary`,
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
      setAttributeIfChanged(rowGroup, "aria-label", `${tableLabel} rows`);

      rows.forEach((row, rowIndex) => {
        setAttributeIfChanged(row, "tabindex", rowIndex === 0 ? "0" : "-1");
      });
      cells.forEach((cell) => {
        setAttributeIfChanged(cell, "tabindex", "-1");
      });
    });

  treeGrid?.querySelectorAll<HTMLElement>('[role="row"]').forEach((row) => {
    if (
      row.closest('[aria-hidden="true"], .ag-hidden') ||
      row.offsetParent === null
    ) {
      setAttributeIfChanged(row, "tabindex", "-1");
      return;
    }

    setAttributeIfChanged(row, "tabindex", "0");
  });

  container
    .querySelectorAll<HTMLInputElement>(
      '.ag-checkbox-input-wrapper input[type="checkbox"]',
    )
    .forEach((checkboxInput) => {
      const cell = checkboxInput.closest<HTMLElement>(
        '[role="gridcell"], [role="columnheader"]',
      );
      const checkboxLabel = checkboxInput.getAttribute("aria-label");
      if (!cell || !checkboxLabel) return;

      const valueText =
        cell
          .querySelector<HTMLElement>(".ag-cell-value, .ag-header-cell-text")
          ?.textContent?.trim() || "";
      const combinedLabel = valueText
        ? `${valueText}, ${checkboxLabel}`
        : checkboxLabel;

      setAttributeIfChanged(cell, "aria-label", combinedLabel);
    });
}

export function useAgGridAccessibilityPatch(tableLabel: string) {
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
      patchGridAccessibility(containerRef.current, tableLabel);
    }
  }, [tableLabel]);

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
      attributeFilter: [
        "aria-hidden",
        "class",
        "role",
        "tabindex",
        "aria-label",
      ],
    });
    schedulePatch();

    return () => {
      observer.disconnect();
      clearScheduledPatch();
    };
  }, [clearScheduledPatch, schedulePatch]);

  return { containerRef, schedulePatch };
}
