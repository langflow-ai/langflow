import { render, screen } from "@testing-library/react";
import AppHeader from "../index";

// i18n — returns the key so aria-label values are predictable
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    "aria-label": ariaLabel,
    "data-testid": testId,
    unstyled,
    ...props
  }: any) => (
    <button aria-label={ariaLabel} data-testid={testId} {...props}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: any) => <>{children}</>,
}));

jest.mock("@/components/common/modelProviderCountComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/alerts/alertDropDown", () => ({
  __esModule: true,
  default: ({ children }: any) => <>{children}</>,
}));

jest.mock("@/assets/LangflowLogo.svg?react", () => ({
  __esModule: true,
  default: () => <svg data-testid="langflow-logo" />,
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
  CustomOrgSelector: () => null,
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("@/customization/hooks/use-custom-theme", () => ({
  __esModule: true,
  default: () => ({ dark: false }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => ({
    notificationCenter: false,
    setNotificationCenter: jest.fn(),
  }),
}));

jest.mock("./components/FlowMenu", () => ({ FlowMenu: () => null }), {
  virtual: true,
});
jest.mock("../components/FlowMenu", () => ({
  __esModule: true,
  default: () => null,
}));

describe("AppHeader — accessible button names", () => {
  beforeEach(() => {
    render(<AppHeader />);
  });

  it("home/back button has an aria-label", () => {
    const btn = screen.getByTestId("icon-ChevronLeft");
    expect(btn.closest("button")).toHaveAttribute("aria-label", "header.home");
  });

  it("notification bell button has an aria-label", () => {
    const btn = screen.getByTestId("notification_button");
    expect(btn).toHaveAttribute("aria-label", "header.notifications");
  });
});
