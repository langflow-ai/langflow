import { fireEvent, render, screen } from "@testing-library/react";
import { ActionPickerAddButton } from "../AddButton";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

describe("ActionPickerAddButton", () => {
  it("should trigger onClick when pressed", () => {
    const onClick = jest.fn();
    render(<ActionPickerAddButton onClick={onClick} testId="decisions" />);
    fireEvent.click(screen.getByTestId("actionpicker-add-decisions"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("should not render a search input (the popover was removed)", () => {
    render(<ActionPickerAddButton onClick={jest.fn()} testId="decisions" />);
    expect(screen.queryByPlaceholderText(/search/i)).not.toBeInTheDocument();
  });
});
