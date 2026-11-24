import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../tooltip";

const renderTooltip = () =>
  render(
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger>Stop build</TooltipTrigger>
        <TooltipContent>Stops the current flow build</TooltipContent>
      </Tooltip>
    </TooltipProvider>,
  );

describe("Tooltip accessibility", () => {
  it("should_have_no_axe_violations_when_visible", async () => {
    const user = userEvent.setup();
    renderTooltip();

    await user.hover(screen.getByRole("button", { name: "Stop build" }));
    await screen.findByRole("tooltip");

    // Radix portals tooltip content to document.body, outside the render
    // container. The region rule is a page-level landmark concern that a
    // bare unit render cannot satisfy.
    expect(
      await axe(document.body, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });

  it("should_show_tooltip_on_keyboard_focus", async () => {
    const user = userEvent.setup();
    renderTooltip();

    await user.tab();
    expect(screen.getByRole("button", { name: "Stop build" })).toHaveFocus();
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      "Stops the current flow build",
    );
  });

  it("should_describe_trigger_via_aria_describedby", async () => {
    const user = userEvent.setup();
    renderTooltip();

    const trigger = screen.getByRole("button", { name: "Stop build" });
    await user.hover(trigger);
    const tooltip = await screen.findByRole("tooltip");

    expect(trigger).toHaveAttribute("aria-describedby", tooltip.id);
  });
});
