import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import RenderKey from "../index";

// Modifier keys render as icons (or a bare glyph), which carry no text for a
// screen reader. Force the macOS branch so every icon-rendered modifier is
// exercised in one file.
jest.mock("@/constants/constants", () => ({
  ...jest.requireActual("@/constants/constants"),
  IS_MAC: true,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} aria-hidden="true" />
  ),
}));

describe("RenderKey accessibility", () => {
  it.each([
    ["shift", "ArrowBigUp", "Shift"],
    ["alt", "OptionIcon", "Option"],
    ["mod", "Command", "Command"],
    ["cmd", "Command", "Command"],
  ])(
    "should_expose_a_text_alternative_for_%s",
    (value, iconName, accessibleText) => {
      render(<RenderKey value={value} />);

      expect(screen.getByTestId(`icon-${iconName}`)).toBeInTheDocument();
      expect(screen.getByText(accessibleText)).toHaveClass("sr-only");
    },
  );

  it("should_name_the_bare_control_glyph", () => {
    render(<RenderKey value="ctrl" />);

    const glyph = screen.getByText("⌃");
    expect(glyph).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("Control")).toHaveClass("sr-only");
  });

  it("should_leave_plain_text_keys_untouched", () => {
    render(<RenderKey value="k" />);

    expect(screen.getByText("K")).toBeInTheDocument();
  });

  it("should_have_no_axe_violations", async () => {
    const { container } = render(<RenderKey value="mod" />);

    expect(await axe(container)).toHaveNoViolations();
  });
});
