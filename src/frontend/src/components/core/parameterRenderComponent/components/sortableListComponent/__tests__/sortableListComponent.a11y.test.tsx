import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import SortableListComponent from "..";

jest.mock(
  "@/CustomNodes/GenericNode/components/ListSelectionComponent",
  () => ({
    __esModule: true,
    default: () => null,
  }),
);

const baseProps = {
  value: [],
  id: "sortable-list-field",
  editNode: false,
  disabled: false,
  placeholder: "Select an item",
  handleOnNewValue: jest.fn(),
};

describe("SortableListComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">Connected tools</span>
        <SortableListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: label only, not composed with the placeholder text —
  // role="combobox" gets special handling from screen readers, same
  // reasoning as connectionComponent.
  it("uses the field's real label as the combobox trigger's accessible name", () => {
    render(
      <>
        <span id="field-label">Connected tools</span>
        <SortableListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("combobox", { name: "Connected tools" }),
    ).toBeInTheDocument();
  });

  it("does not set aria-labelledby on the combobox trigger when absent", () => {
    render(<SortableListComponent {...baseProps} />);

    expect(screen.getByRole("combobox")).not.toHaveAttribute("aria-labelledby");
  });
});
