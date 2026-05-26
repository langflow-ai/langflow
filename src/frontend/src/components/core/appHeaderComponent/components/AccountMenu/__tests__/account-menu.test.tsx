import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { useUtilityStore } from "@/stores/utilityStore";
import { AccountMenu } from "../index";

jest.mock("react-icons/fa", () => ({
  FaDiscord: () => <span data-testid="discord-icon" />,
  FaGithub: () => <span data-testid="github-icon" />,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => <span data-testid="icon-component" />,
  ForwardedIconComponent: () => <span data-testid="forwarded-icon-component" />,
}));

jest.mock("@/controllers/API/queries/auth", () => ({
  useLogout: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/customization/components/custom-profile-icon", () => ({
  CustomProfileIcon: () => <div data-testid="custom-profile-icon" />,
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_DATASTAX_LANGFLOW: false,
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (
    selector: (state: { isAdmin: boolean; autoLogin: boolean }) => unknown,
  ) => selector({ isAdmin: false, autoLogin: false }),
}));

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: (
    selector: (state: { version: string; latestVersion: string }) => unknown,
  ) => selector({ version: "1.0.0", latestVersion: "1.0.0" }),
}));

jest.mock("../../HeaderMenu/index", () => ({
  HeaderMenu: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  HeaderMenuToggle: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
  HeaderMenuItems: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
  HeaderMenuItemButton: ({
    children,
    onClick,
  }: {
    children: ReactNode;
    onClick?: () => void;
  }) => <button onClick={onClick}>{children}</button>,
  HeaderMenuItemLink: ({ children }: { children: ReactNode }) => (
    <a>{children}</a>
  ),
}));

jest.mock("../../ThemeButtons/index", () => ({
  __esModule: true,
  default: () => <div data-testid="theme-buttons" />,
}));

describe("AccountMenu", () => {
  beforeEach(() => {
    act(() => {
      useUtilityStore.setState({ hideLogoutButton: false });
    });
  });

  afterEach(() => {
    act(() => {
      useUtilityStore.setState({ hideLogoutButton: false });
    });
  });

  it("shows logout when hideLogoutButton is false", () => {
    render(<AccountMenu />);

    expect(screen.getByRole("button", { name: /logout/i })).toBeInTheDocument();
  });

  it("hides logout when hideLogoutButton is true", () => {
    act(() => {
      useUtilityStore.setState({ hideLogoutButton: true });
    });

    render(<AccountMenu />);

    expect(
      screen.queryByRole("button", { name: /logout/i }),
    ).not.toBeInTheDocument();
  });
});
