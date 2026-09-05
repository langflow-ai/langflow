import { render, screen } from "@testing-library/react";
import type { AxiosError } from "axios";
import { customShouldSkipAuthRefresh } from "../../utils/custom-should-skip-auth-refresh";
import { CustomAdminPageMenuItem } from "../custom-admin-page-menu-item";
import { CustomHeaderMenuItemsTitle } from "../custom-header-menu-items-title";
import CustomLoginBrandTitle from "../custom-login-brand-title";
import CustomLoginSignupPrompt from "../custom-login-signup-prompt";
import CustomLoginSsoOptions from "../custom-login-sso-options";
import CustomResourceShareAction from "../custom-resource-share-action";
import CustomSettingsPasswordFormGate from "../custom-settings-password-form-gate";

describe("OSS auth customization seams", () => {
  it("does not render admin navigation", () => {
    const { container } = render(
      <CustomAdminPageMenuItem onNavigate={jest.fn()} />,
    );

    expect(container).toBeEmptyDOMElement();
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

  it("keeps non-flow share entry points inert in OSS", () => {
    const { container } = render(
      <CustomResourceShareAction
        resourceId="resource-1"
        resourceType="project"
        resourceName="Project one"
      />,
    );

    expect(container).toBeEmptyDOMElement();
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
