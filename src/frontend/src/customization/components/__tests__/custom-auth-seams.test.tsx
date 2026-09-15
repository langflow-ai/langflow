import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AxiosError } from "axios";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { customShouldSkipAuthRefresh } from "../../utils/custom-should-skip-auth-refresh";
import { CustomAdminPageMenuItem } from "../custom-admin-page-menu-item";
import CustomFlowShareAction from "../custom-flow-share-action";
import { CustomHeaderMenuItemsTitle } from "../custom-header-menu-items-title";
import CustomLoginBrandTitle from "../custom-login-brand-title";
import CustomLoginSignupPrompt from "../custom-login-signup-prompt";
import CustomLoginSsoOptions from "../custom-login-sso-options";
import CustomResourceShareAction from "../custom-resource-share-action";
import CustomSettingsPasswordFormGate from "../custom-settings-password-form-gate";

const mockCapabilities = jest.fn();
const mockPermissions = jest.fn();

jest.mock("@/controllers/API/queries/authorization", () => ({
  useGetAuthorizationCapabilities: () => mockCapabilities(),
}));

jest.mock("@/contexts/permissionsContext", () => ({
  usePermissions: () => mockPermissions(),
}));

jest.mock("@/components/core/appHeaderComponent/components/HeaderMenu", () => ({
  HeaderMenuItemButton: ({
    children,
    onClick,
  }: {
    children: React.ReactNode;
    onClick: () => void;
  }) => (
    <button type="button" onClick={onClick}>
      {children}
    </button>
  ),
}));

describe("OSS auth customization seams", () => {
  beforeEach(() => {
    mockCapabilities.mockReturnValue({
      data: { enforcement_active: false, service_ready: false },
      isLoading: false,
      isError: false,
    });
    mockPermissions.mockReturnValue({
      capability: jest.fn(() => false),
      isUnavailable: true,
    });
  });

  it("does not render collaboration navigation when the server contract is unavailable", () => {
    const { container } = render(
      <CustomAdminPageMenuItem onNavigate={jest.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("renders member navigation only after the server reports readiness", () => {
    const onNavigate = jest.fn();
    mockCapabilities.mockReturnValue({
      data: {
        enforcement_active: true,
        service_ready: true,
        can_administer_platform: false,
      },
      isLoading: false,
      isError: false,
    });

    render(<CustomAdminPageMenuItem onNavigate={onNavigate} />);

    fireEvent.click(screen.getByTestId("menu-teams-button"));
    expect(onNavigate).toHaveBeenCalledWith("/teams");
    expect(screen.getByTestId("menu-shared-with-me-button")).toBeVisible();
    expect(screen.queryByTestId("menu-admin-teams-button")).toBeNull();
  });

  it("gives platform admins one destination for user and team administration", () => {
    const onNavigate = jest.fn();
    mockCapabilities.mockReturnValue({
      data: {
        enforcement_active: true,
        service_ready: true,
        can_administer_platform: true,
      },
      isLoading: false,
      isError: false,
    });

    render(<CustomAdminPageMenuItem onNavigate={onNavigate} />);

    expect(screen.queryByTestId("menu-admin-teams-button")).toBeNull();
    expect(screen.getByTestId("menu-admin-users-button")).toBeVisible();
    fireEvent.click(screen.getByTestId("menu-admin-users-button"));
    expect(onNavigate).toHaveBeenCalledWith("/admin");
  });

  it("keeps user administration available when collaboration is explicitly disabled", () => {
    const onNavigate = jest.fn();
    mockCapabilities.mockReturnValue({
      data: {
        enforcement_active: false,
        service_ready: false,
        can_administer_platform: true,
      },
    });
    render(<CustomAdminPageMenuItem onNavigate={onNavigate} />);
    fireEvent.click(screen.getByTestId("menu-admin-users-button"));
    expect(onNavigate).toHaveBeenCalledWith("/admin");
    expect(screen.queryByTestId("menu-admin-teams-button")).toBeNull();
  });

  it("does not render an account-menu identity header", () => {
    const { container } = render(<CustomHeaderMenuItemsTitle />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders the OSS product name as the login brand", () => {
    render(<CustomLoginBrandTitle />);

    expect(screen.getByText("Langflow")).toBeInTheDocument();
  });

  it("passes signup prompt children through", () => {
    render(
      <CustomLoginSignupPrompt>
        <p>Don't have an account? Sign Up</p>
      </CustomLoginSignupPrompt>,
    );

    expect(
      screen.getByText("Don't have an account? Sign Up"),
    ).toBeInTheDocument();
  });

  it("passes the settings password form through", () => {
    render(
      <CustomSettingsPasswordFormGate>
        <p>Password settings</p>
      </CustomSettingsPasswordFormGate>,
    );

    expect(screen.getByText("Password settings")).toBeInTheDocument();
  });

  it("renders no SSO login options", () => {
    const { container } = render(<CustomLoginSsoOptions />);

    expect(container).toBeEmptyDOMElement();
  });

  it("keeps project sharing inert until server and resource capabilities agree", () => {
    const { container } = render(
      <CustomResourceShareAction
        resourceId="resource-1"
        resourceType="project"
        resourceName="Project one"
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("does not initialize project authorization hooks for unsupported resources", () => {
    mockCapabilities.mockClear();
    mockPermissions.mockClear();

    const { container } = render(
      <CustomResourceShareAction
        resourceId="knowledge-base-1"
        resourceType="knowledge_base"
        resourceName="Knowledge base one"
      />,
    );

    expect(container).toBeEmptyDOMElement();
    expect(mockCapabilities).not.toHaveBeenCalled();
    expect(mockPermissions).not.toHaveBeenCalled();
  });

  it("renders project Share for an authorized owner", () => {
    mockCapabilities.mockReturnValue({
      data: {
        enforcement_active: true,
        service_ready: true,
        user_team_sharing_supported: true,
      },
      isLoading: false,
      isError: false,
    });
    mockPermissions.mockReturnValue({
      capability: jest.fn(() => true),
      isUnavailable: false,
    });

    render(
      <CustomResourceShareAction
        resourceId="resource-1"
        resourceType="project"
        resourceName="Project one"
        display="label"
        onShare={jest.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: /Share Project one/i }),
    ).toBeVisible();
  });

  it("closes the editor menu before requesting the flow sharing dialog", async () => {
    const user = userEvent.setup();
    const onShare = jest.fn();
    mockCapabilities.mockReturnValue({
      data: {
        enforcement_active: true,
        service_ready: true,
        user_team_sharing_supported: true,
      },
      isLoading: false,
      isError: false,
    });
    mockPermissions.mockReturnValue({
      capability: jest.fn(() => true),
      isUnavailable: false,
    });

    render(
      <DropdownMenu>
        <DropdownMenuTrigger>Open sharing menu</DropdownMenuTrigger>
        <DropdownMenuContent>
          <CustomFlowShareAction
            resourceId="flow-1"
            resourceType="flow"
            resourceName="Flow one"
            onShare={onShare}
          />
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    const trigger = screen.getByRole("button", { name: "Open sharing menu" });
    await user.click(trigger);
    await user.click(screen.getByTestId("share-flow-flow-1"));

    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(onShare).toHaveBeenCalledTimes(1);
  });

  it("does not skip auth refresh for an ordinary 403", () => {
    const error = {
      response: { status: 403, data: { detail: "must_change_password" } },
    } as AxiosError;

    expect(customShouldSkipAuthRefresh(error)).toBe(false);
  });

  it("skips auth refresh for a tier denial carried on the error-code header", () => {
    const error = {
      response: {
        status: 403,
        headers: { "x-langflow-error-code": "tier_limit_reached" },
        data: { detail: { error_code: "tier_limit_reached", message: "nope" } },
      },
    } as unknown as AxiosError;

    expect(customShouldSkipAuthRefresh(error)).toBe(true);
  });

  it("skips auth refresh for a feature gate carried only in the body", () => {
    const error = {
      response: {
        status: 403,
        data: {
          detail: { error_code: "feature_not_in_tier", message: "upgrade" },
        },
      },
    } as unknown as AxiosError;

    expect(customShouldSkipAuthRefresh(error)).toBe(true);
  });

  it("skips auth refresh for a tier denial readable only through headers.get", () => {
    // Axios v1 hands the interceptor an AxiosHeaders instance, where the header
    // is reachable through get() and not as a plain own property. The body here
    // carries no error code, so only the get() fallback can answer.
    const error = {
      response: {
        status: 403,
        headers: {
          get: (name: string) =>
            name === "x-langflow-error-code" ? "tier_limit_reached" : undefined,
        },
        data: { detail: { message: "nope" } },
      },
    } as unknown as AxiosError;

    expect(customShouldSkipAuthRefresh(error)).toBe(true);
  });

  it("does not skip auth refresh for an unrelated error code", () => {
    const error = {
      response: {
        status: 403,
        headers: { "x-langflow-error-code": "superuser_required" },
      },
    } as unknown as AxiosError;

    expect(customShouldSkipAuthRefresh(error)).toBe(false);
  });
});
