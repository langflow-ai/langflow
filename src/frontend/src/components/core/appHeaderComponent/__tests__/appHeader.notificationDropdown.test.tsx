import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { axe } from "@/utils/a11y-test";
import AppHeader from "../index";

// This suite intentionally leaves @/alerts/alertDropDown unmocked — index.tsx
// wraps ShadTooltip's child in a SECOND AlertDropdown (see the outer/inner
// pair around the notification button), which mounts two independent
// Popovers on the same trigger. That's invisible under the pass-through
// mock used by appHeader.a11y.test.tsx, so it needs real-DOM coverage here.
jest.mock("@/assets/LangflowLogo.svg?react", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/components/common/modelProviderCountComponent", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/customization/components/custom-AccountMenu", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/customization/components/custom-langflow-counts", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/customization/components/custom-org-selector", () => ({
  __esModule: true,
  CustomOrgSelector: () => null,
}));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));
jest.mock("../components/FlowMenu", () => ({
  __esModule: true,
  default: () => null,
}));

const renderHeader = () =>
  render(
    <TooltipProvider>
      <AppHeader />
    </TooltipProvider>,
  );

describe("AppHeader notification dropdown (real AlertDropdown, unmocked)", () => {
  it("should_have_no_axe_violations when closed", async () => {
    const { container } = renderHeader();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("opens exactly one notification popover, not a duplicate nested one", () => {
    renderHeader();

    fireEvent.click(screen.getByTestId("notification_button"));

    expect(screen.getAllByTestId("notification-dropdown-content")).toHaveLength(
      1,
    );
  });

  it("should_have_no_axe_violations when the notification popover is open", async () => {
    const { container } = renderHeader();

    fireEvent.click(screen.getByTestId("notification_button"));

    expect(await axe(container)).toHaveNoViolations();
  });
});
