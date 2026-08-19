import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { mockGenericIconComponent } from "../../__tests__/a11y-mock-helpers";
import TableNodeComponent from "..";

jest.mock("@/modals/tableModal", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/components/common/genericIconComponent", () =>
  mockGenericIconComponent(),
);

const baseProps = {
  value: [],
  id: "table-field",
  editNode: false,
  disabled: false,
  columns: [],
  description: "",
  tableTitle: "Table",
  handleOnNewValue: jest.fn(),
};

describe("TableNodeComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">Lookup table</span>
        <TableNodeComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: the visible trigger text defaults to the generic
  // "Open Table" (unless a custom trigger_text is configured), so it carries
  // no field context on its own — aria-labelledby must be applied, same
  // reasoning as dataDisplayComponent.
  it("uses the field's real label as the trigger's accessible name", () => {
    render(
      <>
        <span id="field-label">Lookup table</span>
        <TableNodeComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Lookup table" }),
    ).toBeInTheDocument();
  });

  it("falls back to no accessible-name override when ariaLabelledBy is absent", () => {
    render(<TableNodeComponent {...baseProps} />);

    const button = screen.getByRole("button", { name: "Open Table" });
    expect(button).not.toHaveAttribute("aria-labelledby");
  });

  // A configured trigger_text still needs the field label to win over it,
  // since custom trigger text is often just as generic ("View", "Edit").
  it("prefers the field label over a custom trigger_text when both are present", () => {
    render(
      <>
        <span id="field-label">Lookup table</span>
        <TableNodeComponent
          {...baseProps}
          trigger_text="Edit"
          ariaLabelledBy="field-label"
        />
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Lookup table" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
  });
});
