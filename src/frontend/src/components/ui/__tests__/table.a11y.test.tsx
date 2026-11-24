import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../table";

const renderTable = () =>
  render(
    <Table>
      <TableCaption>Registered users</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>Username</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell>admin</TableCell>
          <TableCell>Edit</TableCell>
        </TableRow>
      </TableBody>
    </Table>,
  );

describe("Table accessibility", () => {
  it("should_have_no_axe_violations_with_caption", async () => {
    const { container } = renderTable();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_table_with_caption_and_headers", () => {
    renderTable();

    expect(
      screen.getByRole("table", { name: "Registered users" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Username" }),
    ).toBeInTheDocument();
  });

  // Known gap (a11y-action-plan 3.5): TableHead renders <th> without
  // scope="col", so header/data-cell association is not explicit. Fails
  // until the fix lands.
  it("should_set_column_scope_on_header_cells", () => {
    renderTable();

    const header = screen.getByRole("columnheader", { name: "Username" });
    expect(header).toHaveAttribute("scope", "col");
  });
});
