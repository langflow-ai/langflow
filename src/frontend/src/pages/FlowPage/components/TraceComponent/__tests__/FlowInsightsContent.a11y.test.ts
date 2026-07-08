import { applyRowTabIndices } from "@/components/core/parameterRenderComponent/components/tableComponent/utils/applyRowTabIndices";

function makeGrid(rowCount: number): HTMLElement {
  const container = document.createElement("div");
  const colsContainer = document.createElement("div");
  colsContainer.className = "ag-center-cols-container";

  for (let i = 0; i < rowCount; i++) {
    const row = document.createElement("div");
    row.setAttribute("role", "row");
    colsContainer.appendChild(row);
  }

  container.appendChild(colsContainer);
  return container;
}

describe("applyRowTabIndices — rowgroup tabbable fix", () => {
  it("sets tabindex=0 on the first row and -1 on all others", () => {
    const container = makeGrid(3);
    applyRowTabIndices(container);

    const rows = container.querySelectorAll<HTMLElement>("[role='row']");
    expect(rows[0].getAttribute("tabindex")).toBe("0");
    expect(rows[1].getAttribute("tabindex")).toBe("-1");
    expect(rows[2].getAttribute("tabindex")).toBe("-1");
  });

  it("handles a single row — that row gets tabindex=0", () => {
    const container = makeGrid(1);
    applyRowTabIndices(container);

    const rows = container.querySelectorAll<HTMLElement>("[role='row']");
    expect(rows[0].getAttribute("tabindex")).toBe("0");
  });

  it("does nothing when containerEl is null", () => {
    expect(() => applyRowTabIndices(null)).not.toThrow();
  });

  it("does nothing when there are no rows", () => {
    const container = makeGrid(0);
    applyRowTabIndices(container);

    const rows = container.querySelectorAll("[role='row']");
    expect(rows.length).toBe(0);
  });

  it("overwrites any existing tabindex on rows", () => {
    const container = makeGrid(2);
    const rows = container.querySelectorAll<HTMLElement>("[role='row']");
    rows[0].setAttribute("tabindex", "5");
    rows[1].setAttribute("tabindex", "5");

    applyRowTabIndices(container);

    expect(rows[0].getAttribute("tabindex")).toBe("0");
    expect(rows[1].getAttribute("tabindex")).toBe("-1");
  });
});
