// The global mock from jest.setup.js replaces this component with null;
// unmock it here so the real implementation is under test.
jest.unmock("@/components/common/genericIconComponent");

// Icons load through lazy dynamic imports that never settle in jsdom;
// resolve to a simple svg component so the loaded state is reachable.
// Must be an object-style component (forwardRef): real icons are
// lazy/forwardRef objects, and a plain function would be treated as a
// setState updater by setTargetIcon.
jest.mock("@/utils/styleUtils", () => {
  const { forwardRef } = jest.requireActual("react");
  return {
    getCachedIcon: () => null,
    getNodeIcon: () =>
      Promise.resolve(
        forwardRef(
          (
            { isDark: _isDark, ...props }: Record<string, unknown>,
            ref: unknown,
          ) => <svg ref={ref as React.Ref<SVGSVGElement>} {...props} />,
        ),
      ),
  };
});

import { render, screen } from "@testing-library/react";

const ForwardedIconComponent = jest.requireActual(
  "@/components/common/genericIconComponent",
).default;

// The component loads its icon asynchronously; await the loaded icon so the
// state updates happen inside the test (avoids act() warnings).
const renderIconAndWait = async () => {
  const view = render(<ForwardedIconComponent name="Check" />);
  await screen.findByTestId("icon-Check");
  return view;
};

describe("ForwardedIconComponent accessibility", () => {
  it("should_render_icon_wrapper", async () => {
    const { container } = await renderIconAndWait();

    expect(container.firstElementChild).not.toBeNull();
  });

  // a11y-action-plan 0.3: icons are decorative by default and must be
  // hidden from assistive technology unless an ariaLabel is provided.
  it("should_hide_decorative_icons_from_AT_by_default", async () => {
    await renderIconAndWait();

    expect(screen.getByTestId("icon-Check")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });

  it("should_expose_icon_when_labeled", async () => {
    render(<ForwardedIconComponent name="Check" ariaLabel="Success" />);
    const icon = await screen.findByTestId("icon-Check");

    expect(icon).toHaveAttribute("role", "img");
    expect(icon).toHaveAttribute("aria-label", "Success");
    expect(icon).not.toHaveAttribute("aria-hidden");
  });
});
