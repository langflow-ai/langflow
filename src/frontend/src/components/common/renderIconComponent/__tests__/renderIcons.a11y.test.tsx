import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import RenderIcons from "../index";

// WebKit does not carry sr-only text into AG Grid cell values, so the
// shortcut wrapper must expose an explicit accessible name and hide the
// icon-based visuals (LE-2041 QA round). Force the macOS branch so modifier
// keys resolve to their spoken names.
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

describe("RenderIcons accessibility", () => {
  it("should_name_the_shortcut_with_spoken_modifiers", () => {
    render(<RenderIcons filteredShortcut={["mod", "shift", "a"]} />);

    expect(
      screen.getByRole("img", { name: "Command Shift A" }),
    ).toBeInTheDocument();
  });

  it("should_hide_the_visual_keys_from_the_accessibility_tree", () => {
    render(<RenderIcons filteredShortcut={["mod", "s"]} />);

    const wrapper = screen.getByRole("img", { name: "Command S" });
    expect(wrapper.children.length).toBeGreaterThan(0);
    for (const child of Array.from(wrapper.children)) {
      expect(child).toHaveAttribute("aria-hidden", "true");
    }
  });

  it("should_name_bare_control_shortcuts", () => {
    render(<RenderIcons filteredShortcut={["ctrl", "k"]} />);

    expect(screen.getByRole("img", { name: "Control K" })).toBeInTheDocument();
  });

  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <RenderIcons filteredShortcut={["mod", "shift", "a"]} />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });
});
