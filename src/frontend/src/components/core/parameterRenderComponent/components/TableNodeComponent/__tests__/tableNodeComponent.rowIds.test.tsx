import { act, render } from "@testing-library/react";
import type { ColumnField } from "@/types/utils/functions";
import { hasTableRowIds } from "@/utils/table-row-ids";
import { mockGenericIconComponent } from "../../__tests__/a11y-mock-helpers";
import TableNodeComponent from "..";

// biome-ignore lint/suspicious/noExplicitAny: captured grid props
let modalProps: any;

jest.mock("@/modals/tableModal", () => ({
  __esModule: true,
  // biome-ignore lint/suspicious/noExplicitAny: captured grid props
  default: (props: any) => {
    modalProps = props;
    return <>{props.children}</>;
  },
}));

jest.mock("@/components/common/genericIconComponent", () =>
  mockGenericIconComponent(),
);

type Row = Record<string, unknown>;

const columns = [
  { name: "key", display_name: "Key" },
  { name: "value", display_name: "Value" },
] as ColumnField[];

function renderTable(value: Row[], extra: Record<string, unknown> = {}) {
  const handleOnNewValue = jest.fn();
  render(
    <TableNodeComponent
      value={value}
      id="headers"
      editNode={false}
      disabled={false}
      columns={columns}
      tableTitle="Headers"
      description=""
      handleOnNewValue={handleOnNewValue}
      {...extra}
    />,
  );
  return handleOnNewValue;
}

describe("TableNodeComponent row ids", () => {
  const legacy = [
    { key: "Accept", value: "json" },
    { key: "Auth", value: "x" },
  ];

  it("keys grid rows by their row id", () => {
    renderTable(legacy);

    const rows: Row[] = modalProps.rowData;
    expect(hasTableRowIds(rows)).toBe(true);
    expect(rows.map((row) => modalProps.getRowId({ data: row }))).toEqual(
      rows.map((row) => row._id),
    );
  });

  it("writes nothing when an unedited legacy table is saved", () => {
    const handleOnNewValue = renderTable(legacy);

    act(() => modalProps.onSave());

    expect(handleOnNewValue).not.toHaveBeenCalled();
  });

  it("writes a legacy table whole, with ids, on its first edit", () => {
    const handleOnNewValue = renderTable(legacy);

    act(() => modalProps.addRow());
    act(() => modalProps.onSave());

    const saved: Row[] = handleOnNewValue.mock.calls[0][0].value;
    expect(saved).toHaveLength(3);
    expect(hasTableRowIds(saved)).toBe(true);
    expect(saved.slice(0, 2).map((row) => row.key)).toEqual(["Accept", "Auth"]);
  });

  it("gives an added row a new id after the last row", () => {
    const rows = [
      { _id: "r1", _pos: "a0", key: "Accept", value: "json" },
      { _id: "r2", _pos: "a1", key: "Auth", value: "x" },
    ];
    const handleOnNewValue = renderTable(rows);

    act(() => modalProps.addRow());
    act(() => modalProps.onSave());

    const saved: Row[] = handleOnNewValue.mock.calls[0][0].value;
    expect(saved.slice(0, 2)).toEqual(rows);
    expect(saved[2]).toMatchObject({ _pos: "a2", key: null, value: null });
    expect(saved[2]._id).not.toMatch(/^r[12]$/);
  });

  it("never shows the row keys as columns", () => {
    renderTable([{ _id: "r1", _pos: "a0", name: "x" }], { columns: undefined });

    const fields = modalProps.columnDefs.map(
      (column: { field?: string }) => column.field,
    );
    expect(fields).toEqual(["name"]);
  });
});
