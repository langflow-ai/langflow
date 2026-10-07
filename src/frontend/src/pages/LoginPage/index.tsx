import * as Form from "@radix-ui/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { useContext, useState } from "react";
import { useTranslation } from "react-i18next";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import { extractApiErrorMessage } from "@/controllers/API/helpers/extract-api-error-message";
import { useLoginUser } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
import CustomLoginBrandTitle from "@/customization/components/custom-login-brand-title";
import CustomLoginFormGate from "@/customization/components/custom-login-form-gate";
import CustomLoginSignupPrompt from "@/customization/components/custom-login-signup-prompt";
import CustomLoginSsoOptions from "@/customization/components/custom-login-sso-options";
import useTheme from "@/customization/hooks/use-custom-theme";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { useSanitizeRedirectUrl } from "@/hooks/use-sanitize-redirect-url";
import {
  appendErrorSuggestion,
  getRequiredFieldError,
} from "@/utils/authErrorMessages";
import InputComponent from "../../components/core/parameterRenderComponent/components/inputComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { CONTROL_LOGIN_STATE } from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import useAlertStore from "../../stores/alertStore";
import type { LoginType } from "../../types/api";
import type {
  inputHandlerEventType,
  loginInputStateType,
} from "../../types/components";
import DotGridBackground from "./components/dot-grid-background";

export default function LoginPage(): JSX.Element {
  const [inputState, setInputState] =
    useState<loginInputStateType>(CONTROL_LOGIN_STATE);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  // Server-side rejection (e.g. wrong credentials), mirrored inline so the
  // error is programmatically associated with the credential fields
  // (WCAG 3.3.1) instead of living only in the transient toast.
  const [serverError, setServerError] = useState<string | null>(null);

  const { password, username } = inputState;

  useSanitizeRedirectUrl();
  useTheme();

  const { t } = useTranslation();
  useDocumentTitle(t("auth.signInButton"));
  const { login, clearAuthSession } = useContext(AuthContext);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
    setServerError(null);
  }

  const { mutate } = useLoginUser();
  const queryClient = useQueryClient();

  function signIn() {
    const user: LoginType = {
      username: username.trim(),
      password: password.trim(),
    };

    mutate(user, {
      onSuccess: (data) => {
        clearAuthSession();
        login(data.access_token, "login", data.refresh_token);
        queryClient.clear();
      },
      onError: (error) => {
        const message = appendErrorSuggestion(
          extractApiErrorMessage(
            error as Parameters<typeof extractApiErrorMessage>[0],
            t("errors.signin"),
          ),
          t("errors.signinSuggestion", {
            defaultValue: "Check your username and password, then try again.",
          }),
        );
        setServerError(message);
        setErrorData({
          title: t("errors.signin"),
          list: [message],
        });
      },
    });
  }

  const usernameError = getRequiredFieldError(
    submitAttempted,
    username,
    t("auth.usernameRequired"),
  );
  const passwordError = getRequiredFieldError(
    submitAttempted,
    password,
    t("auth.passwordRequired"),
  );

  return (
    <Form.Root
      onInvalidCapture={() => setSubmitAttempted(true)}
      onSubmit={(event) => {
        setSubmitAttempted(true);
        if (username.trim() === "" || password.trim() === "") {
          event.preventDefault();
          return;
        }
        signIn();
        const _data = Object.fromEntries(new FormData(event.currentTarget));
        event.preventDefault();
      }}
      className="min-h-svh w-full overflow-auto bg-canvas text-foreground"
    >
      <DotGridBackground />
      <main className="relative z-10 flex min-h-svh w-full flex-col items-center justify-center px-6 py-10">
        <div className="flex w-full max-w-[420px] flex-col items-center gap-8">
          <div className="flex items-center gap-2">
            <LangflowLogo
              title={t("common.langflowLogo")}
              className="h-12 w-12 text-foreground"
            />
            <h1 className="pl-3 text-center text-5xl font-semibold tracking-tight">
              <CustomLoginBrandTitle />
            </h1>
          </div>
          <section
            aria-labelledby="login-form-title"
            className="w-full rounded-xl border border-border bg-card p-8 shadow-2xl shadow-black/10 dark:shadow-black/40 sm:p-10"
          >
            <h2 id="login-form-title" className="sr-only">
              {t("auth.loginTitle")}
            </h2>
            <div className="flex flex-col gap-5">
              <CustomLoginFormGate>
                <Form.Field name="username" className="pb-3">
                  <label
                    htmlFor="login-username"
                    className={`mb-2 flex items-center gap-1 overflow-hidden text-sm font-medium ${
                      usernameError ? "label-invalid" : ""
                    }`}
                  >
                    <span className="truncate">{t("auth.usernameLabel")}</span>
                    <span className="shrink-0 font-medium text-destructive">
                      *
                    </span>
                  </label>

                  <Input
                    id="login-username"
                    name="username"
                    type="text"
                    allowAutofill
                    autoComplete="username"
                    onChange={({ target: { value } }) => {
                      handleInput({ target: { name: "username", value } });
                    }}
                    value={username}
                    className="h-11 w-full rounded-lg bg-muted"
                    required
                    aria-describedby={
                      [
                        usernameError && "login-username-error",
                        serverError && "login-form-error",
                      ]
                        .filter(Boolean)
                        .join(" ") || undefined
                    }
                    aria-invalid={Boolean(usernameError || serverError)}
                    placeholder={t("auth.usernamePlaceholder")}
                  />

                  {usernameError && (
                    <p
                      id="login-username-error"
                      role="alert"
                      className="field-invalid"
                    >
                      {usernameError}
                    </p>
                  )}
                </Form.Field>

                <Form.Field name="password" className="pb-3">
                  <label
                    htmlFor="form-login-password"
                    className={`mb-2 flex items-center gap-1 overflow-hidden text-sm font-medium ${
                      passwordError ? "label-invalid" : ""
                    }`}
                  >
                    <span className="truncate">{t("auth.passwordLabel")}</span>
                    <span className="shrink-0 font-medium text-destructive">
                      *
                    </span>
                  </label>

                  <InputComponent
                    onChange={(value) => {
                      handleInput({ target: { name: "password", value } });
                    }}
                    value={password}
                    isForm
                    allowAutofill
                    password={true}
                    required
                    id="login-password"
                    inputProps={{
                      autoComplete: "current-password",
                      "aria-describedby":
                        [
                          passwordError && "login-password-error",
                          serverError && "login-form-error",
                        ]
                          .filter(Boolean)
                          .join(" ") || undefined,
                      "aria-invalid":
                        Boolean(passwordError || serverError) || undefined,
                    }}
                    placeholder={t("auth.passwordPlaceholder")}
                    className="h-11 w-full rounded-lg bg-muted"
                  />

                  {passwordError && (
                    <p
                      id="login-password-error"
                      role="alert"
                      className="field-invalid"
                    >
                      {passwordError}
                    </p>
                  )}
                </Form.Field>

                {serverError && (
                  <p
                    id="login-form-error"
                    role="alert"
                    className="field-invalid static"
                  >
                    {serverError}
                  </p>
                )}

                <Form.Submit asChild>
                  <Button className="h-11 w-full rounded-lg" type="submit">
                    {t("auth.signInButton")}
                  </Button>
                </Form.Submit>
              </CustomLoginFormGate>

              <CustomLoginSsoOptions />

              <CustomLoginSignupPrompt>
                <p className="text-center text-sm text-muted-foreground">
                  {t("auth.noAccount")}{" "}
                  <CustomLink
                    className="font-medium text-primary underline-offset-4 hover:underline"
                    to="/signup"
                  >
                    {t("auth.signUpLink")}
                  </CustomLink>
                </p>
              </CustomLoginSignupPrompt>
            </div>
          </section>
        </div>
      </main>
    </Form.Root>
  );
}
