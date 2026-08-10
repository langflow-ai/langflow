import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import type { APIClassType } from "@/types/api";
import ListSelectionComponent from "../index";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} aria-hidden="true" />
  ),
}));

beforeAll(() => {
  // jsdom does not implement scrollIntoView, which ListItem calls on focus.
  Element.prototype.scrollIntoView = jest.fn();
});

const baseProps: ComponentProps<typeof ListSelectionComponent> = {
  id: "list-selection",
  value: "",
  editNode: false,
  disabled: false,
  handleOnNewValue: jest.fn(),
  open: true,
  onClose: jest.fn(),
  options: [{ name: "Alpha" }, { name: "Beta" }],
  setSelectedList: jest.fn(),
  selectedList: [],
};

describe("ListSelectionComponent accessibility", () => {
  it("should_name_the_dialog_when_it_only_renders_a_search_field", () => {
    // dialog-with-no-close injects no fallback title, so without a DialogTitle
    // this dialog had no accessible name at all.
    render(<ListSelectionComponent {...baseProps} />);

    expect(
      screen.getByRole("dialog", { name: "Select an option" }),
    ).toBeInTheDocument();
  });

  it("should_name_the_search_field", () => {
    render(<ListSelectionComponent {...baseProps} />);

    expect(
      screen.getByRole("textbox", { name: "Search list" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("search_bar_input")).toBeInTheDocument();
  });

  it("should_use_the_component_name_as_the_dialog_title", () => {
    render(
      <ListSelectionComponent
        {...baseProps}
        // Only the two fields the header reads; the full APIClassType shape is
        // irrelevant to the dialog name.
        nodeClass={
          {
            display_name: "Compose Action",
            icon: "Bot",
          } as APIClassType
        }
      />,
    );

    expect(
      screen.getByRole("dialog", { name: "Compose Action" }),
    ).toBeInTheDocument();
  });
});
