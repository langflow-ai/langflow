import { fireEvent, render, waitFor, within } from "@testing-library/react";
import { type ColumnField, FormatterType } from "@/types/utils/functions";
import { FormatColumns } from "@/utils/utils";
import TableComponent from "../index";

type Row = Record<string, unknown>;

// The Knowledge component's Column Configuration schema as the backend ships
// it: `type` only, no `formatter` — or the `text` formatter that saved flows
// persisted after the grid wrote its fallback back into the schema.
function knowledgeColumns(formatter?: FormatterType): ColumnField[] {
  const flag = (name: string, display_name: string): ColumnField => ({
    name,
    display_name,
    sortable: true,
    filterable: true,
    type: "boolean",
    default: false,
    edit_mode: "inline",
    ...(formatter ? { formatter } : {}),
  });
  return [
    {
      name: "column_name",
      display_name: "Column Name",
      sortable: true,
      filterable: true,
      type: "str",
      edit_mode: "inline",
    },
    flag("vectorize", "Vectorize"),
    flag("identifier", "Identifier"),
  ];
}

function renderColumnConfig(rowData: Row[], formatter?: FormatterType) {
  const onUpdate = jest.fn();
  const columns = knowledgeColumns(formatter);
  const result = render(
    <TableComponent
      columnDefs={FormatColumns(columns)}
      context={{}}
      // Same callback-based editability TableNodeComponent passes.
      editable={columns.map((column) => ({
        field: column.name,
        editableCell: true,
        onUpdate,
      }))}
      rowData={rowData}
      suppressColumnVirtualisation
      suppressRowVirtualisation
    />,
  );

  function getToggle(rowIndex: number, field: string) {
    const cell = result.container.querySelector<HTMLElement>(
      `[row-index="${rowIndex}"] [col-id="${field}"]`,
    );
    expect(cell).not.toBeNull();
    return within(cell!).getByRole("switch");
  }

  return { getToggle, onUpdate };
}

describe.each([
  ["without a formatter", undefined],
  ["with a persisted text formatter", FormatterType.text],
])("Knowledge column configuration %s", (_label, formatter) => {
  it("shows every stored flag the way the backend reads it", async () => {
    const rowData = [
      { column_name: "question", vectorize: true, identifier: "true" },
      { column_name: "answer", vectorize: "true", identifier: "false" },
      { column_name: "category", vectorize: "yes", identifier: "" },
      { column_name: "language", vectorize: "False", identifier: false },
    ];
    const { getToggle } = renderColumnConfig(rowData, formatter);
    const checked = (field: string) =>
      rowData.map((_, i) => getToggle(i, field).getAttribute("aria-checked"));

    await waitFor(() => expect(getToggle(0, "vectorize")).toBeChecked());
    expect(checked("vectorize")).toEqual(["true", "true", "true", "false"]);
    expect(checked("identifier")).toEqual(["true", "false", "false", "false"]);
  });

  it("replaces a typed flag with a real boolean when toggled", async () => {
    const rowData = [
      { column_name: "question", vectorize: true, identifier: true },
      { column_name: "answer", vectorize: "false", identifier: false },
    ];
    const { getToggle, onUpdate } = renderColumnConfig(rowData, formatter);

    await waitFor(() => expect(getToggle(1, "vectorize")).toBeEnabled());
    fireEvent.click(getToggle(1, "vectorize"));

    await waitFor(() => expect(rowData[1].vectorize).toBe(true));
    expect(onUpdate).toHaveBeenCalledWith(
      expect.objectContaining({ newValue: true, oldValue: "false" }),
    );
  });

  it("counts a typed identifier toward the single-identifier rule", async () => {
    const rowData = [
      { column_name: "question", vectorize: true, identifier: "True" },
      { column_name: "answer", vectorize: true, identifier: false },
    ];
    const { getToggle } = renderColumnConfig(rowData, formatter);

    await waitFor(() => expect(getToggle(1, "identifier")).toBeDisabled());
    expect(getToggle(0, "identifier")).toBeEnabled();
  });
});
