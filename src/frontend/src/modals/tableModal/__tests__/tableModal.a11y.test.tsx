import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import TableModal from "..";

// TableComponent pulls in ag-grid-react/ag-grid-community, which in this
// Jest setup corrupts unrelated named exports elsewhere in the tree (see
// TableNodeComponent's a11y test for the full writeup) — mocked here so
// only TableModal's own prop-forwarding logic is under test.
jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => ({
    __esModule: true,
    default: function MockTableComponent(props: { tableLabel?: string }) {
      return (
        <div data-testid="mock-table" data-table-label={props.tableLabel} />
      );
    },
  }),
);

const baseProps = {
  tableTitle: "Deployment history",
  description: "d",
  columnDefs: [],
  rowData: [],
  open: true,
};

describe("TableModal", () => {
  // BaseModal portals its content to document.body, outside the render
  // container — same pattern as apiModal/shareModal's axe tests.
  it("should_have_no_axe_violations_when_open", async () => {
    render(
      <TableModal {...baseProps}>
        <button>trigger</button>
      </TableModal>,
    );

    expect(await axe(document.body)).toHaveNoViolations();
  });

  // Regression guard: without forwarding, the grid's own accessible name
  // (setGridAriaProperty + focus-boundary text) falls back to the generic
  // "Data table" translation instead of the title already shown in the
  // modal header.
  it("forwards tableTitle as the grid's tableLabel", () => {
    render(
      <TableModal {...baseProps}>
        <button>trigger</button>
      </TableModal>,
    );

    expect(screen.getByTestId("mock-table")).toHaveAttribute(
      "data-table-label",
      "Deployment history",
    );
  });

  it("lets an explicit tableLabel override tableTitle", () => {
    render(
      <TableModal {...baseProps} tableLabel="Custom grid label">
        <button>trigger</button>
      </TableModal>,
    );

    expect(screen.getByTestId("mock-table")).toHaveAttribute(
      "data-table-label",
      "Custom grid label",
    );
  });
});
