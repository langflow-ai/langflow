import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import FeatureToggles from "../featureTogglesComponent";

const defaultProps = {
  showBeta: false,
  setShowBeta: jest.fn(),
  showLegacy: true,
  setShowLegacy: jest.fn(),
};

describe("FeatureToggles accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(<FeatureToggles {...defaultProps} />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_accessible_names_for_both_switches", () => {
    render(<FeatureToggles {...defaultProps} />);

    expect(
      screen.getByRole("switch", { name: "Show beta components" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: "Show legacy components" }),
    ).toBeInTheDocument();
  });

  it("should_reflect_checked_state_on_the_correctly_named_switch", () => {
    render(<FeatureToggles {...defaultProps} />);

    expect(
      screen.getByRole("switch", { name: "Show beta components" }),
    ).toHaveAttribute("aria-checked", "false");
    expect(
      screen.getByRole("switch", { name: "Show legacy components" }),
    ).toHaveAttribute("aria-checked", "true");
  });
});
