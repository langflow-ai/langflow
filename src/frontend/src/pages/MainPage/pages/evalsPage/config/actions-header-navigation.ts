import type {
  Column,
  ColumnGroup,
  GridApi,
  GridOptions,
  HeaderFocusedEvent,
  NavigateToNextHeaderParams,
  TabToNextHeaderParams,
} from "ag-grid-community";

const ACTIONS_COL_ID = "actions";

function isActions(column: Column | ColumnGroup | undefined): boolean {
  return (
    !!column && "getColId" in column && column.getColId() === ACTIONS_COL_ID
  );
}

function headerBeforeActions(api: GridApi): Column | undefined {
  return api
    .getAllDisplayedColumns()
    .filter((column) => !isActions(column))
    .at(-1);
}

/**
 * Keyboard focus never rests on the actions column header: it is named for screen
 * readers but shows nothing, so a focus ring there frames an empty box.
 */
export const skipActionsHeader: Pick<
  GridOptions,
  "navigateToNextHeader" | "tabToNextHeader" | "onHeaderFocused"
> = {
  navigateToNextHeader: ({ nextHeaderPosition }: NavigateToNextHeaderParams) =>
    isActions(nextHeaderPosition?.column) ? null : nextHeaderPosition,
  // Tab past the last visible header enters the first row, as it would from the actions header.
  tabToNextHeader: ({ nextHeaderPosition, api }: TabToNextHeaderParams) => {
    if (!isActions(nextHeaderPosition?.column))
      return nextHeaderPosition ?? false;
    const first = api.getAllDisplayedColumns()[0];
    return first ? { headerRowIndex: -1, column: first } : false;
  },
  // The other ways in (Up from an actions cell, Shift+Tab from the first cell) land on the previous header.
  onHeaderFocused: ({ column, api }: HeaderFocusedEvent) => {
    if (!isActions(column)) return;
    const previous = headerBeforeActions(api);
    // Deferred: moving focus inside the grid's own focus handling is undone by it.
    if (previous) setTimeout(() => api.setFocusedHeader(previous));
  },
};
