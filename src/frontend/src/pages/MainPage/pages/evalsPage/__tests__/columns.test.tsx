import type { ColDef } from "ag-grid-community";
import {
  datasetColumns,
  datasetItemColumns,
  evaluationColumns,
} from "../config/columns";

const t = (key: string) => key;
const noop = () => undefined;
const byId = (columns: ColDef[], colId: string) =>
  columns.find((column) => column.colId === colId);

describe("evals table columns", () => {
  it("should_name_the_icon_only_actions_column_on_every_evals_table", () => {
    const tables = [
      datasetColumns(t, {
        onOpen: noop,
        onDuplicate: noop,
        onDelete: noop,
      }),
      evaluationColumns(t, { onOpen: noop, onDelete: noop }),
      datasetItemColumns(t, { onEdit: noop, onDelete: noop }),
    ];

    for (const columns of tables) {
      const actions = byId(columns, "actions");
      expect(actions?.headerName).toBe("evals.columnActions");
      expect(actions?.headerClass).toBe("ag-sr-only-header");
    }
  });

  it("should_let_the_pass_rate_header_grow_instead_of_cutting_longer_languages", () => {
    const passRate = byId(
      evaluationColumns(t, { onOpen: noop, onDelete: noop }),
      "pass_rate",
    );

    expect(passRate?.width).toBeUndefined();
    expect(passRate?.flex).toBeGreaterThan(0);
  });
});
