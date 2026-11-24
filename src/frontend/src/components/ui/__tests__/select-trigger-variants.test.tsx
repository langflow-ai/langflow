import { render, screen } from "@testing-library/react";
import type * as ReactTypes from "react";
import { Select, SelectTrigger, SelectValue } from "../select";

// Exercise the Slot 1.3+ `asChild` contract without updating the full Radix
// dependency graph locked for the release branch.
jest.mock("@radix-ui/react-select", () => {
  const actual = jest.requireActual<typeof import("@radix-ui/react-select")>(
    "@radix-ui/react-select",
  );
  const React = jest.requireActual<typeof import("react")>("react");

  const StrictIcon = React.forwardRef<
    ReactTypes.ElementRef<typeof actual.Icon>,
    ReactTypes.ComponentPropsWithoutRef<typeof actual.Icon>
  >(({ asChild, children, ...props }, ref) => {
    if (asChild && !React.isValidElement(children)) {
      throw new Error(
        "Primitive.span failed to slot onto its children. Expected a single React element child or `Slottable`.",
      );
    }

    return (
      <actual.Icon {...props} asChild={asChild} ref={ref}>
        {children}
      </actual.Icon>
    );
  });
  StrictIcon.displayName = "StrictSelectIcon";

  return { ...actual, Icon: StrictIcon };
});

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
