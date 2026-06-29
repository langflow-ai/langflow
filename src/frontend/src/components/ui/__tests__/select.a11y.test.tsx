import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../select";

const renderSelect = (triggerProps: Record<string, unknown> = {}) =>
  render(
    <Select>
      <SelectTrigger {...triggerProps}>
        <SelectValue placeholder="Pick a model" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="gpt">GPT</SelectItem>
        <SelectItem value="claude">Claude</SelectItem>
      </SelectContent>
    </Select>,
  );

describe("Select accessibility", () => {
  // Regression locks: the primitive supports proper naming — the IBM page
  // scans flagged unnamed comboboxes at call sites, not in the primitive.
  it("should_have_no_axe_violations_when_labeled", async () => {
    const { container } = renderSelect({ "aria-label": "Model" });

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_named_combobox_when_labeled", () => {
    renderSelect({ "aria-label": "Model" });

    expect(screen.getByRole("combobox", { name: "Model" })).toBeInTheDocument();
  });

  it("should_expose_collapsed_state_without_stale_controls", () => {
    renderSelect({ "aria-label": "Model" });

    const trigger = screen.getByRole("combobox");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).not.toHaveAttribute("aria-controls");
  });
});
