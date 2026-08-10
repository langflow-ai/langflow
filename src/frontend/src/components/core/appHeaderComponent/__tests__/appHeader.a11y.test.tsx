import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { axe } from "@/utils/a11y-test";
import AppHeader from "../index";

// Mock heavy children — this suite only asserts the header shell semantics
// (landmark + notification bell) owned by AppHeader itself.
jest.mock("@/assets/LangflowLogo.svg?react", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/alerts/alertDropDown", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
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

describe("AppHeader accessibility", () => {
  it("should_render_header_with_notification_button", () => {
    renderHeader();

    expect(screen.getByTestId("app-header")).toBeInTheDocument();
    expect(screen.getByTestId("notification_button")).toBeInTheDocument();
  });

  it("should_expose_header_as_banner_landmark", () => {
    renderHeader();

    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  it("should_name_notification_bell_button", () => {
    renderHeader();

    expect(screen.getByTestId("notification_button")).toHaveAttribute(
      "aria-label",
    );
  });

  it("should_name_home_navigation_button", () => {
    renderHeader();

    expect(screen.getByTestId("icon-ChevronLeft")).toHaveAttribute(
      "aria-label",
      "Go to home",
    );
  });

  it("should_have_no_axe_violations", async () => {
    const { container } = renderHeader();

    expect(await axe(container)).toHaveNoViolations();
  });
});
