import { fireEvent, render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import TabComponent from "../index";

const baseProps = {
  id: "tab-field",
  value: "Option A",
  editNode: false,
  handleOnNewValue: jest.fn(),
  disabled: false,
  options: ["Option A", "Option B", "Option C"],
};

describe("TabComponent accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="tab-label">Mode</span>
        <TabComponent {...baseProps} ariaLabelledBy="tab-label" />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_the_forwarded_field_label_as_the_tablist_accessible_name", () => {
    render(
      <>
        <span id="tab-label">Mode</span>
        <TabComponent {...baseProps} ariaLabelledBy="tab-label" />
      </>,
    );
    expect(screen.getByRole("tablist", { name: "Mode" })).toBeInTheDocument();
  });

  it("should_render_the_tablist_with_no_accessible_name_when_no_field_label_is_forwarded", () => {
    render(<TabComponent {...baseProps} />);
    expect(screen.getByRole("tablist")).not.toHaveAccessibleName();
  });
});

describe("TabComponent — selection still emits real option text", () => {
  // The a11y fix switched Radix's internal `value` to an index token so
  // aria-controls stays a valid single IDREF even when option text contains
  // spaces; this locks in that the *emitted* value is still the real text.
  it("should_emit_the_selected_options_own_text_not_the_internal_index_token", () => {
    const handleOnNewValue = jest.fn();
    render(<TabComponent {...baseProps} handleOnNewValue={handleOnNewValue} />);

    const trigger = screen.getByTestId("tab_1_option_b");
    fireEvent.mouseDown(trigger);
    fireEvent.click(trigger);

    expect(handleOnNewValue).toHaveBeenCalledWith({ value: "Option B" }, {});
  });

  it("should_mark_the_tab_matching_the_incoming_value_as_selected", () => {
    render(<TabComponent {...baseProps} value="Option C" />);

    expect(screen.getByTestId("tab_2_option_c")).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  // Regression guard: a stored value outside validOptions (4th+ option, or
  // truncated by the 20-char limit) must not clamp to "first tab selected" —
  // that would silently misreport what the flow actually holds. No match
  // should mean no trigger is selected, same as before the index-token fix.
  it("should_not_select_any_tab_when_the_stored_value_is_not_among_validOptions", () => {
    render(
      <TabComponent
        {...baseProps}
        options={["Option A", "Option B", "Option C", "Option D"]}
        value="Option D"
      />,
    );

    for (const testId of [
      "tab_0_option_a",
      "tab_1_option_b",
      "tab_2_option_c",
    ]) {
      expect(screen.getByTestId(testId)).toHaveAttribute(
        "aria-selected",
        "false",
      );
    }
  });
});
