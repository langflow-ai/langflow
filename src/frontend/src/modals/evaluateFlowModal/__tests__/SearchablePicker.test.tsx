import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SearchablePicker from "../SearchablePicker";

function renderPicker(onChange = jest.fn()) {
  render(
    <SearchablePicker
      id="evaluation-dataset"
      testId="evaluate-dataset"
      options={[
        { id: "a", label: "Capitals (3 items)" },
        { id: "b", label: "Empty one (0 items)", disabled: true },
        { id: "c", label: "Support triage (12 items)" },
      ]}
      value=""
      onChange={onChange}
      placeholder="Choose a dataset"
      searchPlaceholder="Search datasets"
      emptyText="No dataset matches"
    />,
  );
  return onChange;
}

describe("SearchablePicker", () => {
  // cmdk scrolls the active option into view, which jsdom does not implement.
  beforeEach(() => {
    Element.prototype.scrollIntoView = jest.fn();
  });

  it("should_filter_the_list_by_what_is_typed_and_pick_an_option", async () => {
    const onChange = renderPicker();

    await userEvent.click(screen.getByTestId("evaluate-dataset"));
    await userEvent.type(
      screen.getByTestId("evaluate-dataset-search"),
      "support",
    );

    expect(screen.queryByRole("option", { name: /Capitals/ })).toBeNull();
    await userEvent.click(
      screen.getByRole("option", { name: /Support triage/ }),
    );
    expect(onChange).toHaveBeenCalledWith("c");
  });

  it("should_not_pick_a_disabled_option", async () => {
    const onChange = renderPicker();

    await userEvent.click(screen.getByTestId("evaluate-dataset"));
    await userEvent.click(screen.getByRole("option", { name: /Empty one/ }));

    expect(onChange).not.toHaveBeenCalled();
  });
});
