export function applyRowTabIndices(containerEl: HTMLElement | null): void {
  if (!containerEl) return;
  containerEl
    .querySelectorAll<HTMLElement>(".ag-center-cols-container [role='row']")
    .forEach((row, idx) => {
      row.setAttribute("tabindex", idx === 0 ? "0" : "-1");
    });
}
