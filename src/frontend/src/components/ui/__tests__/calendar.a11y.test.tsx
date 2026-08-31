import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import { Calendar } from "../calendar";

// Fixed month so weekday/day names and the caption never depend on "today".
const JUNE_2024 = new Date(2024, 5, 15);

describe("Calendar accessibility", () => {
  it("should_have_no_axe_violations_in_single_selection_mode", async () => {
    const { container } = render(
      <Calendar mode="single" defaultMonth={JUNE_2024} />,
    );

    // `region` is a page-level landmark rule; the calendar always ships inside
    // a popover or form in the real app.
    expect(
      await axe(container, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });

  it("should_have_no_axe_violations_with_a_selected_day", async () => {
    const { container } = render(
      <Calendar
        mode="single"
        defaultMonth={JUNE_2024}
        selected={JUNE_2024}
        // Disabled days exercise the aria-disabled path alongside selection.
        disabled={{ before: new Date(2024, 5, 10) }}
      />,
    );

    expect(
      await axe(container, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });

  it("should_have_no_axe_violations_in_range_mode", async () => {
    const { container } = render(
      <Calendar
        mode="range"
        defaultMonth={JUNE_2024}
        numberOfMonths={2}
        selected={{ from: JUNE_2024, to: new Date(2024, 5, 20) }}
      />,
    );

    expect(
      await axe(container, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });

  it("should_expose_the_month_as_a_named_grid", () => {
    render(<Calendar mode="single" defaultMonth={JUNE_2024} />);

    // WCAG 1.3.1: the day matrix must be a real grid whose name says which
    // month is shown, otherwise the dates have no context.
    expect(
      screen.getByRole("grid", { name: /June 2024/i }),
    ).toBeInTheDocument();
  });

  it("should_give_the_navigation_buttons_accessible_names", () => {
    render(<Calendar mode="single" defaultMonth={JUNE_2024} />);

    // The chevrons are decorative SVGs, so the buttons must carry their own
    // names (WCAG 4.1.2).
    expect(
      screen.getByRole("button", { name: /previous month/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /next month/i }),
    ).toBeInTheDocument();
  });

  it("should_mark_the_selected_day_as_selected", () => {
    render(
      <Calendar mode="single" defaultMonth={JUNE_2024} selected={JUNE_2024} />,
    );

    // react-day-picker v9 exposes selection on the gridcell `<td>`, not the
    // inner button; the button repeats it in its own label.
    const dayButton = screen.getByRole("button", {
      name: /June 15th, 2024, selected/i,
    });
    expect(dayButton.closest("td")).toHaveAttribute("aria-selected", "true");

    const unselected = screen.getByRole("button", {
      name: /June 18th, 2024/i,
    });
    expect(unselected.closest("td")).not.toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("should_let_a_keyboard_user_select_a_day", async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    render(
      <Calendar
        mode="single"
        defaultMonth={JUNE_2024}
        selected={JUNE_2024}
        onSelect={onSelect}
      />,
    );

    // WCAG 2.1.1: days must be operable from the keyboard, not click-only.
    const day = screen.getByRole("button", { name: /June 18th, 2024/i });
    day.focus();
    await user.keyboard("{Enter}");

    expect(onSelect).toHaveBeenCalled();
  });
});
