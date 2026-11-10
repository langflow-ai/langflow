import { fireEvent, render, screen } from "@testing-library/react";
import MultiselectComponent from "../index";

const baseProps = {
  id: "days",
  editNode: false,
  disabled: false,
  nodeClass: {} as never,
  handleNodeClass: jest.fn(),
  nodeId: "node",
};

// cmdk scrolls the active item into view; jsdom has no layout to scroll.
beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
});

const DAYS = ["Monday", "Tuesday", "Wednesday"];
const LABELS = { Monday: "星期一", Tuesday: "星期二", Wednesday: "星期三" };

describe("MultiselectComponent option labels", () => {
  it("should_show_translated_labels_and_save_the_option_values", () => {
    const save = jest.fn();
    render(
      <MultiselectComponent
        {...baseProps}
        value={["Monday", "Tuesday"]}
        options={DAYS}
        optionLabels={LABELS}
        handleOnNewValue={save}
      />,
    );

    expect(screen.getByTestId("value-dropdown-days")).toHaveTextContent(
      "星期一, 星期二",
    );

    fireEvent.click(screen.getByTestId("days"));
    const wednesday = screen.getByTestId("Wednesday-days-option");
    expect(wednesday).toHaveTextContent("星期三");

    fireEvent.click(wednesday);

    expect(save).toHaveBeenCalledWith({
      value: ["Monday", "Tuesday", "Wednesday"],
    });
  });

  it("should_find_an_option_by_its_translated_label", () => {
    render(
      <MultiselectComponent
        {...baseProps}
        value={[]}
        options={DAYS}
        optionLabels={LABELS}
        handleOnNewValue={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("days"));
    fireEvent.change(screen.getByPlaceholderText(/search/i), {
      target: { value: "星期三" },
    });

    expect(screen.getAllByRole("option")[0]).toHaveAttribute(
      "data-testid",
      "Wednesday-days-option",
    );
  });
});
