import { fireEvent, render, waitFor, within } from "@testing-library/react";
import type { GridApi } from "ag-grid-community";
import { FormatterType } from "@/types/utils/functions";
import { FormatColumns } from "@/utils/utils";
import TableComponent, { type TableComponentProps } from "../index";

type EditableMode = "all" | "fields" | "callbacks";

function renderColumnConfig(
  mode: EditableMode,
  vectorizeField = "vectorize",
  editableCell = true,
) {
  const onUpdate = jest.fn();
  const rowData = [
    { column_name: "question", [vectorizeField]: true, identifier: true },
    { column_name: "answer", [vectorizeField]: false, identifier: false },
    { column_name: "category", [vectorizeField]: false, identifier: false },
  ];
  const fields = [vectorizeField, "identifier"];
  const editable: TableComponentProps["editable"] =
    mode === "all"
      ? true
      : mode === "fields"
        ? fields
        : fields.map((field) => ({
            field,
            editableCell,
            onUpdate,
          }));
  let api: GridApi;
  const result = render(
    <TableComponent
      columnDefs={FormatColumns(
        fields.map((name) => ({
          name,
          display_name: name,
          sortable: false,
          filterable: false,
          formatter: FormatterType.boolean,
          edit_mode: "inline",
        })),
      )}
      context={{}}
      editable={editable}
      rowData={rowData}
      onCellValueChanged={mode === "callbacks" ? undefined : onUpdate}
      onGridReady={(event) => {
        api = event.api;
      }}
      suppressColumnVirtualisation
      suppressRowVirtualisation
    />,
  );

  function getToggle(rowIndex: number, field = vectorizeField) {
    const cell = result.container.querySelector<HTMLElement>(
      `[row-index="${rowIndex}"] [col-id="${field}"]`,
    );
    expect(cell).not.toBeNull();
    return within(cell!).getByRole("switch");
  }

  return { ...result, getApi: () => api, getToggle, onUpdate, rowData };
}

describe.each<EditableMode>(["all", "fields", "callbacks"])(
  "TableComponent vectorization with %s editability",
  (mode) => {
    it.each(["vectorize", "Vectorize"])(
      "edits multiple %s rows independently and reports boolean values",
      async (field) => {
        const { getApi, getToggle, onUpdate, rowData } = renderColumnConfig(
          mode,
          field,
        );
        await waitFor(() => expect(getToggle(1)).toBeEnabled());

        // Both the inline editor and the rendered switch must stay editable.
        const api = getApi();
        const column = api.getColumn(field)!;
        expect(column.isCellEditable(api.getDisplayedRowAtIndex(1)!)).toBe(
          true,
        );

        fireEvent.click(getToggle(1));
        fireEvent.click(getToggle(2));

        await waitFor(() => {
          expect(rowData.map((row) => row[field])).toEqual([true, true, true]);
          expect(getToggle(0)).toBeChecked();
          expect(getToggle(1)).toBeChecked();
          expect(getToggle(2)).toBeChecked();
        });
        expect(onUpdate).toHaveBeenCalledTimes(2);
        expect(onUpdate).toHaveBeenLastCalledWith(
          expect.objectContaining({
            data: rowData[2],
            newValue: true,
            oldValue: false,
          }),
        );

        fireEvent.click(getToggle(0));
        await waitFor(() => {
          expect(rowData.map((row) => row[field])).toEqual([false, true, true]);
          expect(getToggle(0)).not.toBeChecked();
        });
        expect(column.isCellEditable(api.getDisplayedRowAtIndex(0)!)).toBe(
          true,
        );

        fireEvent.click(getToggle(0));
        await waitFor(() => expect(getToggle(0)).toBeChecked());
        expect(rowData.map((row) => row[field])).toEqual([true, true, true]);
        expect(rowData.map((row) => row.identifier)).toEqual([
          true,
          false,
          false,
        ]);

        // Saving the table reads these same grid rows.
        const savedRows: unknown[] = [];
        api.forEachNode((node) => savedRows.push(node.data));
        expect(savedRows).toEqual(rowData);
      },
    );

    it("preserves the identifier single-selection behavior", async () => {
      const { getApi, getToggle, rowData } = renderColumnConfig(mode);
      await waitFor(() => expect(getToggle(1, "identifier")).toBeDisabled());
      const api = getApi();
      expect(
        api
          .getColumn("identifier")!
          .isCellEditable(api.getDisplayedRowAtIndex(1)!),
      ).toBe(false);

      fireEvent.click(getToggle(0, "identifier"));
      // Callback-based editors refresh the grid without a parent re-render.
      await waitFor(() => expect(getToggle(1, "identifier")).toBeEnabled());
      fireEvent.click(getToggle(1, "identifier"));
      await waitFor(() => expect(getToggle(0, "identifier")).toBeDisabled());
      expect(rowData.map((row) => row.identifier)).toEqual([
        false,
        true,
        false,
      ]);
    });
  },
);

it("keeps explicitly read-only vectorize cells disabled", async () => {
  const { getApi, getToggle, onUpdate, rowData } = renderColumnConfig(
    "callbacks",
    "vectorize",
    false,
  );
  await waitFor(() => expect(getToggle(1)).toBeDisabled());
  expect(getToggle(0)).toBeDisabled();
  const api = getApi();
  expect(
    api.getColumn("vectorize")!.isCellEditable(api.getDisplayedRowAtIndex(1)!),
  ).toBe(false);

  fireEvent.click(getToggle(1));
  expect(onUpdate).not.toHaveBeenCalled();
  expect(rowData.map((row) => row.vectorize)).toEqual([true, false, false]);
});
