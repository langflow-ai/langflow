// The global mock from jest.setup.js replaces this component with null;
// unmock it here so the real implementation is under test.
jest.unmock("@/components/common/genericIconComponent");

import { render } from "@testing-library/react";

const ForwardedIconComponent = jest.requireActual(
  "@/components/common/genericIconComponent",
).default;

describe("ForwardedIconComponent accessibility", () => {
  it("should_render_icon_wrapper", () => {
    const { container } = render(<ForwardedIconComponent name="Check" />);

    expect(container.firstElementChild).not.toBeNull();
  });

  // Known gap (a11y-action-plan 0.3): the icon wrapper exposes no a11y
  // props (ariaHidden / ariaLabel / title) and decorative icons are not
  // hidden from assistive technology by default.
  it("should_hide_decorative_icons_from_AT_by_default", () => {
    const { container } = render(<ForwardedIconComponent name="Check" />);

    const rendered = container.firstElementChild;
    expect(rendered).not.toBeNull();
    expect(rendered).toHaveAttribute("aria-hidden", "true");
  });
});
