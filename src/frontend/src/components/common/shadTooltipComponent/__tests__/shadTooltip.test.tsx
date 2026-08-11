import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";

// jest.setup.js globally mocks ShadTooltip to just render children (for the
// convenience of every other test suite) — bypass that here with
// requireActual since this file tests ShadTooltip's own real behavior.
const ShadTooltip = jest.requireActual("../index").default;

let lastTriggerProps: Record<string, unknown> = {};

jest.mock("@/components/ui/tooltip", () => {
  const actual = jest.requireActual("@/components/ui/tooltip");
  return {
    ...actual,
    TooltipTrigger: ({
      children,
      ...props
    }: {
      children: React.ReactNode;
      [key: string]: unknown;
    }) => {
      lastTriggerProps = props;
      return <>{children}</>;
    },
  };
});

describe("ShadTooltip ariaDescribedBy override", () => {
  beforeEach(() => {
    lastTriggerProps = {};
  });

  it("passes aria-describedby=undefined through to suppress the description when explicitly requested", () => {
    render(
      <TooltipProvider>
        <ShadTooltip content="Component settings" ariaDescribedBy={undefined}>
          <button aria-label="Component settings">X</button>
        </ShadTooltip>
      </TooltipProvider>,
    );

    expect(
      screen.getByRole("button", { name: "Component settings" }),
    ).toBeInTheDocument();
    expect("aria-describedby" in lastTriggerProps).toBe(true);
    expect(lastTriggerProps["aria-describedby"]).toBeUndefined();
  });

  it("passes a custom aria-describedby id through when given a string", () => {
    render(
      <TooltipProvider>
        <ShadTooltip content="Hint" ariaDescribedBy="custom-desc-id">
          <button aria-label="Settings">X</button>
        </ShadTooltip>
      </TooltipProvider>,
    );

    expect("aria-describedby" in lastTriggerProps).toBe(true);
    expect(lastTriggerProps["aria-describedby"]).toBe("custom-desc-id");
  });

  it("does not touch aria-describedby at all when the prop is omitted, preserving Radix's default", () => {
    render(
      <TooltipProvider>
        <ShadTooltip content="Some hint">
          <button aria-label="Settings">X</button>
        </ShadTooltip>
      </TooltipProvider>,
    );

    expect("aria-describedby" in lastTriggerProps).toBe(false);
  });
});
