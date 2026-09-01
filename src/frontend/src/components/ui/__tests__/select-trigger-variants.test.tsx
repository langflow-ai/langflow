import { render, screen } from "@testing-library/react";
import { Select, SelectTrigger, SelectValue } from "../select";

const renderTrigger = (triggerProps: Record<string, unknown> = {}) =>
  render(
    <Select>
      <SelectTrigger data-testid="trigger" {...triggerProps}>
        <SelectValue placeholder="Pick a model" />
      </SelectTrigger>
    </Select>,
  );

describe("SelectTrigger variants", () => {
  // Radix's `asChild` swaps the primitive for its single element child, so the
  // plain variant must omit the icon entirely. Rendering `<Select.Icon asChild>`
  // with no children throws "Primitive.span failed to slot onto its children"
  // on @radix-ui/react-slot >= 1.3, taking the whole tree down.
  it("should_render_no_icon_for_plain_variant", () => {
    expect(() => renderTrigger({ variant: "plain" })).not.toThrow();

    expect(screen.getByTestId("trigger").querySelector("svg")).toBeNull();
  });

  it("should_render_chevron_for_default_variant", () => {
    renderTrigger();

    expect(screen.getByTestId("trigger").querySelector("svg")).not.toBeNull();
  });
});
