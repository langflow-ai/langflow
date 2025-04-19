/**
 * @file LoginPage/index.tsx
 * @description Login page component that handles both traditional username/password
 * login and Keycloak/SSO authentication.
 * Supports a configurable "forceSSO" mode that hides the username/password form.
 */
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import { useLoginUser } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
import { useKeycloakAuth } from "@/hooks/useKeycloakAuth";
import * as Form from "@radix-ui/react-form";
import { useContext, useState } from "react";
import InputComponent from "../../components/core/parameterRenderComponent/components/inputComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { SIGNIN_ERROR_ALERT } from "../../constants/alerts_constants";
import { CONTROL_LOGIN_STATE } from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import useAlertStore from "../../stores/alertStore";
import { LoginType } from "../../types/api";
import {
  inputHandlerEventType,
  loginInputStateType,
} from "../../types/components";

/**
 * Login page component that supports both traditional and SSO authentication.
 *
 * This component handles:
 * 1. Traditional username/password authentication
 * 2. Keycloak/SSO authentication when enabled
 * 3. Force SSO mode that hides username/password form when configured
 *
 * @returns The login page JSX element
 */
export default function LoginPage(): JSX.Element {
  // State for username and password inputs
  const [inputState, setInputState] =
    useState<loginInputStateType>(CONTROL_LOGIN_STATE);

  const { password, username } = inputState;
  const { login } = useContext(AuthContext);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  // Get Keycloak configuration and functions from the hook
  const {
    isKeycloakEnabled, // Whether Keycloak is enabled
    isForceSSO, // Whether to hide username/password login
    redirectToKeycloakLogin, // Function to redirect to Keycloak
    isLoading: isKeycloakLoading,
  } = useKeycloakAuth();

  /**
   * Handles input changes for the login form
   */
  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  // API mutation for traditional login
  const { mutate } = useLoginUser();

  /**
   * Handles traditional username/password sign in
   * Authenticates the user and handles success/error cases
   */
  function signIn() {
    const user: LoginType = {
      username: username.trim(),
      password: password.trim(),
    };

    mutate(user, {
      onSuccess: (data) => {
        login(data.access_token, "login", data.refresh_token);
      },
      onError: (error) => {
        setErrorData({
          title: SIGNIN_ERROR_ALERT,
          list: [error["response"]["data"]["detail"]],
        });
      },
    });
  }

  /**
   * Handles SSO login by redirecting to Keycloak
   * This is called when the user clicks the "Sign in with SSO" button
   */
  function handleKeycloakLogin() {
    redirectToKeycloakLogin();
  }

  // Show loading spinner while Keycloak config is being fetched
  if (isKeycloakLoading) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center bg-muted">
        <div className="flex flex-col items-center justify-center">
          <div className="h-10 w-10 animate-spin rounded-full border-b-2 border-t-2 border-primary"></div>
        </div>
      </div>
    );
  }

  /**
   * Renders the login form with conditional sections based on SSO configuration:
   * - With SSO disabled: Shows only username/password form
   * - With SSO enabled: Shows both username/password form and SSO button
   * - With Force SSO: Shows only SSO button
   */
  return (
    <Form.Root
      onSubmit={(event) => {
        if (password === "") {
          event.preventDefault();
          return;
        }
        signIn();
        const data = Object.fromEntries(new FormData(event.currentTarget));
        event.preventDefault();
      }}
      className="h-screen w-full"
    >
      <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
        <div className="flex w-72 flex-col items-center justify-center gap-2">
          {/* Logo section */}
          <LangflowLogo
            title="Langflow logo"
            className="mb-4 h-10 w-10 scale-[1.5]"
          />
          <span className="mb-6 text-2xl font-semibold text-primary">
            Sign in to Langflow
          </span>

          {/* Username/password login form - conditionally rendered based on forceSSO setting */}
          {(!isKeycloakEnabled || !isForceSSO) && (
            <>
              <div className="mb-3 w-full">
                <Form.Field name="username">
                  <Form.Label className="data-[invalid]:label-invalid">
                    Username{" "}
                    <span className="font-medium text-destructive">*</span>
                  </Form.Label>

                  <Form.Control asChild>
                    <Input
                      type="username"
                      onChange={({ target: { value } }) => {
                        handleInput({ target: { name: "username", value } });
                      }}
                      value={username}
                      className="w-full"
                      required
                      placeholder="Username"
                    />
                  </Form.Control>

                  <Form.Message match="valueMissing" className="field-invalid">
                    Please enter your username
                  </Form.Message>
                </Form.Field>
              </div>
              <div className="mb-3 w-full">
                <Form.Field name="password">
                  <Form.Label className="data-[invalid]:label-invalid">
                    Password{" "}
                    <span className="font-medium text-destructive">*</span>
                  </Form.Label>

                  <InputComponent
                    onChange={(value) => {
                      handleInput({ target: { name: "password", value } });
                    }}
                    value={password}
                    isForm
                    password={true}
                    required
                    placeholder="Password"
                    className="w-full"
                  />

                  <Form.Message className="field-invalid" match="valueMissing">
                    Please enter your password
                  </Form.Message>
                </Form.Field>
              </div>
              <div className="w-full">
                <Form.Submit asChild>
                  <Button className="mr-3 mt-6 w-full" type="submit">
                    Sign in
                  </Button>
                </Form.Submit>
              </div>
            </>
          )}

          {/* SSO login button section - only shown when Keycloak is enabled */}
          {isKeycloakEnabled && (
            <>
              {/* "Or" divider - only shown when both login options are available */}
              {!isForceSSO && (
                <div className="grid w-full justify-items-center">
                  <div className="m-8 text-xs uppercase text-muted-foreground">
                    Or
                  </div>
                </div>
              )}

              <div className="w-full">
                <Button
                  className="w-full"
                  variant="default"
                  type="button"
                  onClick={handleKeycloakLogin}
                  ignoreTitleCase={true}
                >
                  Sign in with SSO
                </Button>
              </div>
            </>
          )}

          {/* Sign up link - only shown when not in force SSO mode */}
          {(!isKeycloakEnabled || !isForceSSO) && (
            <div className="mt-3 w-full">
              <CustomLink to="/signup">
                <Button className="w-full" variant="ghost" type="button">
                  Don't have an account?&nbsp;<b>Sign Up</b>
                </Button>
              </CustomLink>
            </div>
          )}
        </div>
      </div>
    </Form.Root>
  );
}
