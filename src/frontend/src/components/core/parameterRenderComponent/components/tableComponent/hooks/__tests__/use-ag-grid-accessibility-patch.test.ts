import {
  patchDisabledPagingButtons,
  patchEmptyRowGroups,
  patchTabbableRow,
  patchTabGuards,
} from "../use-ag-grid-accessibility-patch";

describe("patchDisabledPagingButtons", () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
  });

  function makePagingButton(disabled: boolean) {
    const button = document.createElement("div");
    button.classList.add("ag-button", "ag-paging-button");
    button.setAttribute("role", "button");
    button.setAttribute("tabindex", "0");
    if (disabled) {
      button.classList.add("ag-disabled");
      button.setAttribute("aria-disabled", "true");
    }
    container.appendChild(button);
    return button;
  }

  it("removes disabled paging buttons from the tab order", () => {
    const button = makePagingButton(true);

    patchDisabledPagingButtons(container);

    expect(button.getAttribute("tabindex")).toBe("-1");
  });

  it("keeps enabled paging buttons in the tab order", () => {
    const button = makePagingButton(false);

    patchDisabledPagingButtons(container);

    expect(button.getAttribute("tabindex")).toBe("0");
  });

  it("restores tabindex when a button becomes enabled again", () => {
    const button = makePagingButton(true);
    patchDisabledPagingButtons(container);
    expect(button.getAttribute("tabindex")).toBe("-1");

    button.classList.remove("ag-disabled");
    button.setAttribute("aria-disabled", "false");
    patchDisabledPagingButtons(container);

    expect(button.getAttribute("tabindex")).toBe("0");
  });

  it("treats aria-disabled=true as disabled even without the class", () => {
    const button = makePagingButton(false);
    button.setAttribute("aria-disabled", "true");

    patchDisabledPagingButtons(container);

    expect(button.getAttribute("tabindex")).toBe("-1");
  });

  it("does nothing when there are no paging buttons", () => {
    expect(() => patchDisabledPagingButtons(container)).not.toThrow();
  });
});

describe("patchTabGuards", () => {
  const labels = {
    startFocusBoundary: "Start of Test table",
    endFocusBoundary: "End of Test table",
  };

  it("gives tab guards a valid widget role and an accessible name", () => {
    const container = document.createElement("div");
    const start = document.createElement("div");
    start.className = "ag-tab-guard ag-tab-guard-top";
    start.setAttribute("role", "presentation");
    start.setAttribute("tabindex", "0");
    const end = document.createElement("div");
    end.className = "ag-tab-guard ag-tab-guard-bottom";
    end.setAttribute("role", "presentation");
    end.setAttribute("tabindex", "0");
    container.append(start, end);

    patchTabGuards(container, labels);

    expect(start.getAttribute("role")).toBe("button");
    expect(start.getAttribute("aria-label")).toBe("Start of Test table");
    expect(end.getAttribute("role")).toBe("button");
    expect(end.getAttribute("aria-label")).toBe("End of Test table");
  });
});

describe("patchEmptyRowGroups", () => {
  it("demotes empty rowgroups to presentation and keeps populated ones", () => {
    const container = document.createElement("div");
    const empty = document.createElement("div");
    empty.setAttribute("role", "rowgroup");
    const populated = document.createElement("div");
    populated.setAttribute("role", "rowgroup");
    const row = document.createElement("div");
    row.setAttribute("role", "row");
    populated.appendChild(row);
    container.append(empty, populated);

    patchEmptyRowGroups(container);

    expect(empty.getAttribute("role")).toBe("presentation");
    expect(populated.getAttribute("role")).toBe("rowgroup");
  });

  it("restores the rowgroup role once a demoted group gains rows", () => {
    const container = document.createElement("div");
    const group = document.createElement("div");
    group.setAttribute("role", "rowgroup");
    container.appendChild(group);

    patchEmptyRowGroups(container);
    expect(group.getAttribute("role")).toBe("presentation");

    const row = document.createElement("div");
    row.setAttribute("role", "row");
    group.appendChild(row);
    patchEmptyRowGroups(container);

    expect(group.getAttribute("role")).toBe("rowgroup");
  });
});

describe("patchTabbableRow", () => {
  it("makes only the first body row tabbable (roving tabindex)", () => {
    const container = document.createElement("div");
    const rowsContainer = document.createElement("div");
    rowsContainer.className = "ag-center-cols-container";
    const rows = [0, 1, 2].map(() => {
      const row = document.createElement("div");
      row.setAttribute("role", "row");
      rowsContainer.appendChild(row);
      return row;
    });
    container.appendChild(rowsContainer);

    patchTabbableRow(container);

    expect(rows[0].getAttribute("tabindex")).toBe("0");
    expect(rows[1].getAttribute("tabindex")).toBe("-1");
    expect(rows[2].getAttribute("tabindex")).toBe("-1");
  });

  it("falls back to the first header row when the body is empty", () => {
    const container = document.createElement("div");
    const header = document.createElement("div");
    header.className = "ag-header";
    const headerRows = [0, 1].map(() => {
      const row = document.createElement("div");
      row.setAttribute("role", "row");
      header.appendChild(row);
      return row;
    });
    const body = document.createElement("div");
    body.className = "ag-center-cols-container";
    container.append(header, body);

    patchTabbableRow(container);

    expect(headerRows[0].getAttribute("tabindex")).toBe("0");
    expect(headerRows[1].getAttribute("tabindex")).toBe("-1");
  });

  it("keeps header rows out of the tab order when body rows exist", () => {
    const container = document.createElement("div");
    const header = document.createElement("div");
    header.className = "ag-header";
    const headerRow = document.createElement("div");
    headerRow.setAttribute("role", "row");
    headerRow.setAttribute("tabindex", "0");
    header.appendChild(headerRow);
    const body = document.createElement("div");
    body.className = "ag-center-cols-container";
    const bodyRow = document.createElement("div");
    bodyRow.setAttribute("role", "row");
    body.appendChild(bodyRow);
    container.append(header, body);

    patchTabbableRow(container);

    expect(bodyRow.getAttribute("tabindex")).toBe("0");
    expect(headerRow.getAttribute("tabindex")).toBe("-1");
  });
});
