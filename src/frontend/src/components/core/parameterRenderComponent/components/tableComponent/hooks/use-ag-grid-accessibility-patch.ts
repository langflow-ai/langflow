import { useCallback, useRef } from "react";

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
  startFocusBoundary: string;
  endFocusBoundary: string;
};

export function isDisabledPagingButton(button: Element) {
  return (
    button.classList.contains("ag-disabled") ||
    button.getAttribute("aria-disabled") === "true"
  );
}

/**
 * AG Grid (v32) leaves disabled pagination buttons (`.ag-paging-button.ag-disabled`)
 * with `tabindex="0"` and only sets `aria-disabled="true"`, so they stay keyboard
 * tab stops (`FOCUSABLE_EXCLUDE` spares `.ag-button`).
 *
 * Demote disabled paging buttons to `tabindex="-1"` and restore enabled ones to
 * `0`. This alone is not enough — AG Grid still *programmatically* focuses a
 * disabled paging button on tab-out (`allowFocusForNextGridCoreContainer`),
 * handled by the focusin redirect in the table component. `inert`/`disabled` are
 * deliberately avoided: they break AG Grid's tab guards, which then dead-stop on
 * `<body>` and trap reverse (Shift+Tab) entry into the grid (WCAG 2.1.2).
 */
export function patchDisabledPagingButtons(container: HTMLElement) {
  container
    .querySelectorAll<HTMLElement>(".ag-paging-button")
    .forEach((button) => {
      setAttributeIfChanged(
        button,
        "tabindex",
        isDisabledPagingButton(button) ? "-1" : "0",
      );
    });
}

/**
 * AG Grid's focus-boundary sentinels (`.ag-tab-guard`) are `tabindex="0"` with
 * `role="presentation"`. A tabbable element with a non-widget role fails IBM's
 * `element_tabbable_role_valid` (WCAG 4.1.2). Give them a valid widget role and
 * an accessible name so a screen reader announces the table's focus boundaries.
 */
export function patchTabGuards(
  container: HTMLElement,
  labels: AgGridAccessibilityLabels,
) {
  container
    .querySelectorAll<HTMLElement>(".ag-tab-guard")
    .forEach((guard, index) => {
      setAttributeIfChanged(guard, "role", "button");
      setAttributeIfChanged(
        guard,
        "aria-label",
        index === 0 ? labels.startFocusBoundary : labels.endFocusBoundary,
      );
    });
}

/**
 * AG Grid renders several `role="rowgroup"` containers (pinned top/bottom,
 * spacers) that never own a `role="row"` child. An empty rowgroup fails IBM's
 * `aria_child_valid` (WCAG 1.3.1). Demote the empty ones to `role="presentation"`
 * and restore the role once they do own rows. A marker attribute lets the patch
 * find the demoted containers again after their role has been changed.
 */
export function patchEmptyRowGroups(container: HTMLElement) {
  container
    .querySelectorAll<HTMLElement>(
      '[role="rowgroup"], [data-langflow-a11y-rowgroup="true"]',
    )
    .forEach((rowGroup) => {
      setAttributeIfChanged(rowGroup, "data-langflow-a11y-rowgroup", "true");
      const hasRows = rowGroup.querySelector('[role="row"]') !== null;
      setAttributeIfChanged(
        rowGroup,
        "role",
        hasRows ? "rowgroup" : "presentation",
      );
    });
}

/**
 * A `treegrid`/`grid` must expose a tabbable `row` so keyboard users can reach
 * its content (IBM `aria_child_tabbable`, WCAG 2.1.1 / 4.1.2). AG Grid keeps all
 * rows at `tabindex="-1"` and relies on its tab guards instead. Apply a roving
 * tabindex: the first rendered body row becomes the grid's single tabbable row,
 * the rest stay `-1`. Actual cell navigation is unchanged (arrow keys / the tab
 * guards still drive focus into cells).
 */
export function patchTabbableRow(container: HTMLElement) {
  const rows = container.querySelectorAll<HTMLElement>(
    '.ag-center-cols-container [role="row"]',
  );
  rows.forEach((row, index) => {
    setAttributeIfChanged(row, "tabindex", index === 0 ? "0" : "-1");
  });
}

export function patchGridAccessibility(
  container: HTMLElement,
  labels: AgGridAccessibilityLabels,
) {
  patchDisabledPagingButtons(container);
  patchTabGuards(container, labels);
  patchEmptyRowGroups(container);
  patchTabbableRow(container);
}

export function useAgGridAccessibilityPatch(labels: AgGridAccessibilityLabels) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const frameRef = useRef<number | undefined>(undefined);
  const labelsRef = useRef(labels);
  labelsRef.current = labels;

  const schedulePatch = useCallback(() => {
    if (frameRef.current !== undefined) {
      cancelAnimationFrame(frameRef.current);
    }
    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = undefined;
      if (containerRef.current) {
        patchGridAccessibility(containerRef.current, labelsRef.current);
      }
    });
  }, []);

  return { containerRef, schedulePatch };
}
