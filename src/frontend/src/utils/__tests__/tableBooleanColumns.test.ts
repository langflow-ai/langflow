import type { ColDef, ValueParserParams } from "ag-grid-community";
import TableAutoCellRender from "@/components/core/parameterRenderComponent/components/tableComponent/components/tableAutoCellRender";
import TableDropdownCellEditor from "@/components/core/parameterRenderComponent/components/tableComponent/components/tableDropdownCellEditor";
import { type ColumnField, FormatterType } from "@/types/utils/functions";
import { FormatColumns, isTruthyCellValue } from "../utils";

// The Knowledge component's Vectorize column exactly as the backend ships it:
// `TableInput.table_schema` declares a `type`, never a `formatter`.
const vectorizeColumn = (
  overrides: Partial<ColumnField> = {},
): ColumnField => ({
  name: "vectorize",
  display_name: "Vectorize",
  sortable: true,
  filterable: true,
  type: "boolean",
  edit_mode: "inline",
  default: false,
  ...overrides,
});

function parse(colDef: ColDef, newValue: unknown) {
  return colDef.valueParser instanceof Function
    ? colDef.valueParser({
        newValue,
        oldValue: false,
        colDef,
        context: {},
      } as ValueParserParams)
    : newValue;
}

describe("isTruthyCellValue", () => {
  // Mirrors lfx's `coalesce_bool`, which is how the backend reads these cells.
  it.each([
    [true, true],
    ["True", true],
    ["true", true],
    ["TRUE", true],
    [" true ", true],
    ["1", true],
    ["t", true],
    ["y", true],
    ["yes", true],
    [1, true],
    [false, false],
    ["False", false],
    ["false", false],
    ["0", false],
    ["no", false],
    ["", false],
    [0, false],
    [null, false],
    [undefined, false],
  ])("reads %p as %p", (value, expected) => {
    expect(isTruthyCellValue(value)).toBe(expected);
  });
});

describe("FormatColumns boolean columns", () => {
  it.each([
    ["without a formatter", undefined],
    ["with the text formatter saved flows persisted", FormatterType.text],
    ["with an explicit boolean formatter", FormatterType.boolean],
  ])("renders a boolean-typed column %s as a toggle", (_label, formatter) => {
    const [colDef] = FormatColumns([vectorizeColumn({ formatter })]);

    expect(colDef.cellRenderer).toBe(TableAutoCellRender);
    expect(colDef.cellRendererParams).toEqual({
      formatter: FormatterType.boolean,
    });
  });

  it("coerces anything committed through the grid to a real boolean", () => {
    const [colDef] = FormatColumns([vectorizeColumn()]);

    expect(parse(colDef, "true")).toBe(true);
    expect(parse(colDef, "TRUE")).toBe(true);
    expect(parse(colDef, "false")).toBe(false);
    expect(parse(colDef, "nope")).toBe(false);
    expect(parse(colDef, true)).toBe(true);
  });

  it("keeps a boolean column that declares options as a dropdown", () => {
    const [colDef] = FormatColumns([
      vectorizeColumn({ options: ["True", "False"], default: "False" }),
    ]);

    expect(colDef.cellEditor).toBe(TableDropdownCellEditor);
    expect(colDef.cellRendererParams).toEqual({
      formatter: FormatterType.text,
    });
    expect(parse(colDef, "True")).toBe("True");
  });

  it("leaves text columns as inline text cells", () => {
    const [colDef] = FormatColumns([
      vectorizeColumn({ name: "column_name", type: "str" }),
    ]);

    expect(colDef.cellRenderer).toBeUndefined();
    expect(colDef.cellEditor).toBeUndefined();
    expect(parse(colDef, "true")).toBe("true");
  });
});
