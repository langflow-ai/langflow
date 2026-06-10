import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

// The header pulls in a lot of chrome that isn't under test; stub everything
// except the logo button whose navigation target this suite pins down.
jest.mock(
  "@/assets/LangflowLogo.svg?react",
  () => ({
    __esModule: true,
    default: () => <svg data-testid="langflow-logo" />,
  }),
  { virtual: true },
);
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/alerts/alertDropDown", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => <span />,
}));
jest.mock("@/components/common/modelProviderCountComponent", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children?: ReactNode }) => <>{children}</>,
}));
jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    ...rest
  }: {
    children?: ReactNode;
    onClick?: () => void;
    [key: string]: unknown;
  }) => (
    <button
      type="button"
      onClick={onClick}
      data-testid={rest["data-testid"] as string | undefined}
    >
      {children}
    </button>
  ),
}));
jest.mock("@/components/ui/separator", () => ({
  Separator: () => null,
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: { notificationCenter: boolean }) => unknown) =>
    selector({ notificationCenter: false }),
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
jest.mock("@/customization/hooks/use-custom-theme", () => ({
  __esModule: true,
  default: () => {},
}));
jest.mock("@/components/core/appHeaderComponent/components/FlowMenu", () => ({
  __esModule: true,
  default: () => null,
}));

const mockNavigate = jest.fn();
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));

import AppHeader from "../index";

describe("AppHeader home navigation", () => {
  it("logo click navigates to /flows (the app home) — '/' is the public landing page", () => {
    render(<AppHeader />);
    fireEvent.click(screen.getByTestId("icon-ChevronLeft"));
    expect(mockNavigate).toHaveBeenCalledWith("/flows");
  });
});
