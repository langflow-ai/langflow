import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { SearchConfigTrigger } from "../searchConfigTrigger";

// searchConfigTrigger.test.tsx mocks Button/ShadTooltip/icon for interaction
// testing, and its Button mock doesn't forward aria-label — so it can't
// actually verify the real accessible name. This suite renders everything
// unmocked to check the real DOM. The global jest.setup.js mock for
// genericIconComponent only stubs the default export, not the named
// ForwardedIconComponent this component actually imports, so override it here.
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: ({ name }: { name?: string }) => (
    <span data-testid={`icon-${name}`} aria-hidden="true" />
  ),
}));
describe("SearchConfigTrigger accessibility (real Button/ShadTooltip, unmocked)", () => {
  it("should_have_no_axe_violations when inactive", async () => {
    const { container } = render(
      <SearchConfigTrigger showConfig={false} setShowConfig={jest.fn()} />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations when active", async () => {
    const { container } = render(
      <SearchConfigTrigger showConfig={true} setShowConfig={jest.fn()} />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("exposes an accessible name on the real button element", () => {
    render(
      <SearchConfigTrigger showConfig={false} setShowConfig={jest.fn()} />,
    );

    expect(
      screen.getByRole("button", { name: "Component settings" }),
    ).toBeInTheDocument();
  });
});
