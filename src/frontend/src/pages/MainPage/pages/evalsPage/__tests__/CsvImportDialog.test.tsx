import { render, screen, within } from "@testing-library/react";
import type { CsvPreview } from "@/controllers/API/queries/evals/types";
import CsvImportDialog from "../components/CsvImportDialog";

// pandas.to_csv writes the index as a first column with an empty header.
const PANDAS_PREVIEW: CsvPreview = {
  headers: ["", "question", "answer"],
  rows: [["0", "What is 2+2?", "4"]],
  total_rows: 1,
};

jest.mock("@/controllers/API/queries/evals/use-datasets", () => ({
  usePreviewCsvImport: () => ({
    mutate: (
      _variables: unknown,
      options: { onSuccess: (data: CsvPreview) => void },
    ) => options.onSuccess(PANDAS_PREVIEW),
    isPending: false,
  }),
  useImportCsv: () => ({ mutate: jest.fn(), isPending: false }),
}));

describe("CsvImportDialog", () => {
  it("should_preview_the_chosen_columns_cells_when_the_csv_has_an_unnamed_index_column", () => {
    render(
      <CsvImportDialog
        datasetId="dataset-1"
        open
        setOpen={jest.fn()}
        initialFile={new File(["x"], "data.csv", { type: "text/csv" })}
      />,
    );

    const cells = within(screen.getByRole("table")).getAllByRole("cell");
    expect(cells.map((cell) => cell.textContent)).toEqual([
      "What is 2+2?",
      "4",
    ]);
  });
});
