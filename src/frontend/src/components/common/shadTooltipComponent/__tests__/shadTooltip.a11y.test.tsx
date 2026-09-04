import { render } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { axe } from "@/utils/a11y-test";

// jest.setup.js globally mocks ShadTooltip to just render children (for the
// convenience of every other test suite) — bypass that here since this file
// needs the real Radix Tooltip/TooltipTrigger/TooltipContent markup. Unlike
// shadTooltip.test.tsx (which mocks TooltipTrigger to inspect prop-passing
// behavior), this file leaves everything real so axe checks the actual DOM.
const ShadTooltip = jest.requireActual("../index").default;

describe("ShadTooltip accessibility (real Radix Tooltip, unmocked)", () => {
  it("should_have_no_axe_violations when closed", async () => {
    const { container } = render(
      <TooltipProvider>
        <ShadTooltip content="Settings">
          <button aria-label="Settings">X</button>
        </ShadTooltip>
      </TooltipProvider>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations when open, with the redundant description suppressed", async () => {
    const { container } = render(
      <TooltipProvider>
        <ShadTooltip content="Settings" open ariaDescribedBy={undefined}>
          <button aria-label="Settings">X</button>
        </ShadTooltip>
      </TooltipProvider>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations when open, with Radix's default aria-describedby intact", async () => {
    const { container } = render(
      <TooltipProvider>
        <ShadTooltip content="Extra detail on hover" open>
          <button aria-label="Settings">X</button>
        </ShadTooltip>
      </TooltipProvider>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });
});
