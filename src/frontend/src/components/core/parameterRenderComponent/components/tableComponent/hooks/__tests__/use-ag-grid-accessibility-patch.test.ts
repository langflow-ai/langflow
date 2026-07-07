import type { AgGridAccessibilityLabels } from "../use-ag-grid-accessibility-patch";
import { patchGridAccessibility } from "../use-ag-grid-accessibility-patch";

describe("patchGridAccessibility", () => {
  const labels: AgGridAccessibilityLabels = {
    endFocusBoundary: "End of table",
    rows: "Table rows",
    startFocusBoundary: "Start of table",
    table: "Test table",
  };

  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
  });

  describe("Bug 1: Hidden row control restoration", () => {
    it("should restore tabindex when hidden row becomes visible", () => {
      const treeGrid = document.createElement("div");
      treeGrid.setAttribute("role", "treegrid");

      const row = document.createElement("div");
      row.setAttribute("role", "row");

      const button = document.createElement("button");
      button.setAttribute("tabindex", "0");
      button.textContent = "Action";

      row.appendChild(button);
      treeGrid.appendChild(row);
      container.appendChild(treeGrid);

      // Initial state: button should be focusable
      expect(button.getAttribute("tabindex")).toBe("0");
      expect(button.hasAttribute("data-langflow-a11y-demoted")).toBe(false);

      // Hide the row and apply patch
      row.classList.add("ag-hidden");
      patchGridAccessibility(container, labels);

      // Button should be demoted and marked
      expect(button.getAttribute("tabindex")).toBe("-1");
      expect(button.hasAttribute("data-langflow-a11y-demoted")).toBe(true);
      expect(button.getAttribute("data-langflow-a11y-demoted")).toBe("0");

      // Show the row again and apply patch
      row.classList.remove("ag-hidden");
      patchGridAccessibility(container, labels);

      // Button should be restored to original tabindex
      expect(button.getAttribute("tabindex")).toBe("0");
      expect(button.hasAttribute("data-langflow-a11y-demoted")).toBe(false);
    });

    it("should restore elements without original tabindex correctly", () => {
      const treeGrid = document.createElement("div");
      treeGrid.setAttribute("role", "treegrid");

      const row = document.createElement("div");
      row.setAttribute("role", "row");

      const link = document.createElement("a");
      link.setAttribute("href", "#");
      link.textContent = "Link";

      row.appendChild(link);
      treeGrid.appendChild(row);
      container.appendChild(treeGrid);

      // Hide the row and apply patch
      row.classList.add("ag-hidden");
      patchGridAccessibility(container, labels);

      // Link should be demoted with empty string stored
      expect(link.getAttribute("tabindex")).toBe("-1");
      expect(link.getAttribute("data-langflow-a11y-demoted")).toBe("");

      // Show the row again and apply patch
      row.classList.remove("ag-hidden");
      patchGridAccessibility(container, labels);

      // Link should have tabindex removed (restored to no tabindex)
      expect(link.hasAttribute("tabindex")).toBe(false);
      expect(link.hasAttribute("data-langflow-a11y-demoted")).toBe(false);
    });

    it("should handle multiple hide/show cycles without losing state", () => {
      const treeGrid = document.createElement("div");
      treeGrid.setAttribute("role", "treegrid");

      const row = document.createElement("div");
      row.setAttribute("role", "row");

      const input = document.createElement("input");
      input.setAttribute("tabindex", "5");

      row.appendChild(input);
      treeGrid.appendChild(row);
      container.appendChild(treeGrid);

      // Cycle 1: Hide
      row.classList.add("ag-hidden");
      patchGridAccessibility(container, labels);
      expect(input.getAttribute("tabindex")).toBe("-1");

      // Cycle 1: Show
      row.classList.remove("ag-hidden");
      patchGridAccessibility(container, labels);
      expect(input.getAttribute("tabindex")).toBe("5");

      // Cycle 2: Hide again
      row.classList.add("ag-hidden");
      patchGridAccessibility(container, labels);
      expect(input.getAttribute("tabindex")).toBe("-1");

      // Cycle 2: Show again
      row.classList.remove("ag-hidden");
      patchGridAccessibility(container, labels);
      expect(input.getAttribute("tabindex")).toBe("5");
    });

    it("should handle elements already at tabindex=-1 correctly", () => {
      const treeGrid = document.createElement("div");
      treeGrid.setAttribute("role", "treegrid");

      const row = document.createElement("div");
      row.setAttribute("role", "row");

      const button = document.createElement("button");
      button.setAttribute("tabindex", "-1");
      button.textContent = "Already disabled";

      row.appendChild(button);
      treeGrid.appendChild(row);
      container.appendChild(treeGrid);

      // Hide the row
      row.classList.add("ag-hidden");
      patchGridAccessibility(container, labels);

      // Button will be marked because it matches 'button' selector
      // The stored value will be "-1"
      expect(button.getAttribute("tabindex")).toBe("-1");
      expect(button.hasAttribute("data-langflow-a11y-demoted")).toBe(true);
      expect(button.getAttribute("data-langflow-a11y-demoted")).toBe("-1");

      // Show the row
      row.classList.remove("ag-hidden");
      patchGridAccessibility(container, labels);

      // Button should be restored to "-1" (its original value)
      expect(button.getAttribute("tabindex")).toBe("-1");
      expect(button.hasAttribute("data-langflow-a11y-demoted")).toBe(false);
    });
  });

  describe("Bug 2: Pagination button self-latching", () => {
    it("should not latch disabled state when class is removed", () => {
      const button = document.createElement("button");
      button.classList.add("ag-paging-button", "ag-disabled");
      container.appendChild(button);

      // Apply patch with disabled class
      patchGridAccessibility(container, labels);
      expect(button.getAttribute("aria-disabled")).toBe("true");
      expect(button.getAttribute("tabindex")).toBe("-1");

      // Remove disabled class (simulating AG Grid re-enable)
      button.classList.remove("ag-disabled");
      patchGridAccessibility(container, labels);

      // Button should now be enabled (not latched)
      expect(button.getAttribute("aria-disabled")).toBe("false");
      expect(button.getAttribute("tabindex")).toBe("0");
    });

    it("should handle enable/disable cycles correctly", () => {
      const prevButton = document.createElement("button");
      prevButton.classList.add("ag-paging-button");
      prevButton.setAttribute("aria-label", "Previous");
      container.appendChild(prevButton);

      // Start enabled
      patchGridAccessibility(container, labels);
      expect(prevButton.getAttribute("aria-disabled")).toBe("false");
      expect(prevButton.getAttribute("tabindex")).toBe("0");

      // Disable (page 1)
      prevButton.classList.add("ag-disabled");
      patchGridAccessibility(container, labels);
      expect(prevButton.getAttribute("aria-disabled")).toBe("true");
      expect(prevButton.getAttribute("tabindex")).toBe("-1");

      // Enable (page 2)
      prevButton.classList.remove("ag-disabled");
      patchGridAccessibility(container, labels);
      expect(prevButton.getAttribute("aria-disabled")).toBe("false");
      expect(prevButton.getAttribute("tabindex")).toBe("0");

      // Disable again (back to page 1)
      prevButton.classList.add("ag-disabled");
      patchGridAccessibility(container, labels);
      expect(prevButton.getAttribute("aria-disabled")).toBe("true");
      expect(prevButton.getAttribute("tabindex")).toBe("-1");
    });

    it("should only use class as input signal, not aria-disabled attribute", () => {
      const button = document.createElement("button");
      button.classList.add("ag-paging-button");
      // Manually set stale aria-disabled (simulating previous patch run)
      button.setAttribute("aria-disabled", "true");
      container.appendChild(button);

      patchGridAccessibility(container, labels);

      // Should be enabled because class is not present
      // (ignoring the stale aria-disabled="true")
      expect(button.getAttribute("aria-disabled")).toBe("false");
      expect(button.getAttribute("tabindex")).toBe("0");
    });
  });

  describe("Integration: Both fixes working together", () => {
    it("should handle pagination and row visibility changes simultaneously", () => {
      const treeGrid = document.createElement("div");
      treeGrid.setAttribute("role", "treegrid");

      const row = document.createElement("div");
      row.setAttribute("role", "row");
      const rowButton = document.createElement("button");
      rowButton.textContent = "Row action";
      row.appendChild(rowButton);
      treeGrid.appendChild(row);

      const pagingButton = document.createElement("button");
      pagingButton.classList.add("ag-paging-button", "ag-disabled");

      container.appendChild(treeGrid);
      container.appendChild(pagingButton);

      // Initial state
      patchGridAccessibility(container, labels);
      expect(pagingButton.getAttribute("aria-disabled")).toBe("true");
      expect(pagingButton.getAttribute("tabindex")).toBe("-1");

      // Hide row and enable pagination
      row.classList.add("ag-hidden");
      pagingButton.classList.remove("ag-disabled");
      patchGridAccessibility(container, labels);

      // Row button should be demoted
      expect(rowButton.getAttribute("tabindex")).toBe("-1");
      expect(rowButton.hasAttribute("data-langflow-a11y-demoted")).toBe(true);

      // Paging button should be enabled
      expect(pagingButton.getAttribute("aria-disabled")).toBe("false");
      expect(pagingButton.getAttribute("tabindex")).toBe("0");

      // Show row and disable pagination
      row.classList.remove("ag-hidden");
      pagingButton.classList.add("ag-disabled");
      patchGridAccessibility(container, labels);

      // Row button should be restored
      expect(rowButton.hasAttribute("tabindex")).toBe(false);
      expect(rowButton.hasAttribute("data-langflow-a11y-demoted")).toBe(false);

      // Paging button should be disabled
      expect(pagingButton.getAttribute("aria-disabled")).toBe("true");
      expect(pagingButton.getAttribute("tabindex")).toBe("-1");
    });
  });

  describe("Other accessibility patches", () => {
    it("should set aria-label on treegrid", () => {
      const treeGrid = document.createElement("div");
      treeGrid.setAttribute("role", "treegrid");
      container.appendChild(treeGrid);

      patchGridAccessibility(container, labels);

      expect(treeGrid.getAttribute("aria-label")).toBe("Test table");
      expect(treeGrid.getAttribute("tabindex")).toBe("0");
    });

    it("should set role and aria-label on tab guards", () => {
      const startGuard = document.createElement("div");
      startGuard.classList.add("ag-tab-guard");
      const endGuard = document.createElement("div");
      endGuard.classList.add("ag-tab-guard");

      container.appendChild(startGuard);
      container.appendChild(endGuard);

      patchGridAccessibility(container, labels);

      expect(startGuard.getAttribute("role")).toBe("button");
      expect(startGuard.getAttribute("aria-label")).toBe("Start of table");
      expect(endGuard.getAttribute("role")).toBe("button");
      expect(endGuard.getAttribute("aria-label")).toBe("End of table");
    });
  });
});
