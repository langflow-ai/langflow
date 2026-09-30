import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import { RadioGroup, RadioGroupItem } from "../radio-group";

const renderRadioGroup = () =>
  render(
    <RadioGroup aria-label="Event delivery" defaultValue="streaming">
      <RadioGroupItem value="streaming" aria-label="Streaming" />
      <RadioGroupItem value="polling" aria-label="Polling" />
    </RadioGroup>,
  );

describe("RadioGroup accessibility", () => {
  it("should_have_no_axe_violations_when_labeled", async () => {
    const { container } = renderRadioGroup();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_radiogroup_role_with_accessible_name", () => {
    renderRadioGroup();

    expect(
      screen.getByRole("radiogroup", { name: "Event delivery" }),
    ).toBeInTheDocument();
  });

  it("should_expose_checked_state", () => {
    renderRadioGroup();

    expect(screen.getByRole("radio", { name: "Streaming" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Polling" })).not.toBeChecked();
  });

  it("should_move_focus_with_arrow_keys", async () => {
    const user = userEvent.setup();
    renderRadioGroup();

    await user.tab();
    expect(screen.getByRole("radio", { name: "Streaming" })).toHaveFocus();

    // Roving focus: arrow keys move focus between radios. (Radix selects
    // on keyboard focus in real browsers, but that path needs layout APIs
    // jsdom lacks, so this only locks the focus contract.)
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("radio", { name: "Polling" })).toHaveFocus();
  });
});
