import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
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

  // Known gap (a11y-action-plan 3.3): the app header is a plain <div>, so
  // there is no banner landmark for AT navigation. Fails until the fix lands.
  it("should_expose_header_as_banner_landmark", () => {
    renderHeader();

    expect(screen.getByRole("banner")).toBeInTheDocument();
  });

  // Known gap (a11y-action-plan 2.3): the notification bell button has no
  // aria-label; its visible label span is CSS-hidden and the Bell icon is
  // the only content. Fails until the fix lands.
  it("should_name_notification_bell_button", () => {
    renderHeader();

    expect(screen.getByTestId("notification_button")).toHaveAttribute(
      "aria-label",
    );
  });

  it("should_name_home_logo_button", () => {
    renderHeader();

    expect(screen.getByTestId("icon-ChevronLeft")).toHaveAttribute(
      "aria-label",
      "Langflow Logo",
    );
  });
});
