import * as Form from "@radix-ui/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { useContext, useState } from "react";
import { useTranslation } from "react-i18next";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { extractApiErrorMessage } from "@/controllers/API/helpers/extract-api-error-message";
import { useLoginUser } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
import CustomLoginSsoOptions from "@/customization/components/custom-login-sso-options";
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

  const { password, username } = inputState;

  useSanitizeRedirectUrl();

  const { t } = useTranslation();
  const { login, clearAuthSession } = useContext(AuthContext);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
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
        setErrorData({
          title: t("errors.signin"),
          list: [
            appendErrorSuggestion(
              extractApiErrorMessage(
                error as Parameters<typeof extractApiErrorMessage>[0],
                t("errors.signin"),
              ),
              t("errors.signinSuggestion", {
                defaultValue:
                  "Check your username and password, then try again.",
              }),
            ),
          ],
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
      className="dark min-h-svh w-full overflow-auto bg-canvas text-foreground"
    >
      <DotGridBackground />
      <main className="relative z-10 flex min-h-svh w-full flex-col items-center justify-center px-6 py-10">
        <div className="flex w-full max-w-[420px] flex-col items-center gap-8">
          <div className="flex items-center gap-2">
            <LangflowLogo
              title={t("common.langflowLogo")}
              className="h-12 w-12 text-foreground"
            />
            <h1 className="pl-2 text-center text-4xl font-semibold tracking-tight">
              {t("auth.loginTitle")}
            </h1>
          </div>
          <section className="w-full rounded-xl border border-border bg-card p-8 shadow-2xl shadow-black/40 sm:p-10">
            <CustomLoginSsoOptions />
            <div className="flex flex-col gap-6">
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
                    usernameError ? "login-username-error" : undefined
                  }
                  aria-invalid={Boolean(usernameError)}
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
                    "aria-describedby": passwordError
                      ? "login-password-error"
                      : undefined,
                    "aria-invalid": Boolean(passwordError) || undefined,
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

              <Form.Submit asChild>
                <Button className="h-11 w-full rounded-lg" type="submit">
                  {t("auth.signInButton")}
                </Button>
              </Form.Submit>

              <CustomLink className="block w-full" to="/signup">
                <ShadTooltip
                  content={`${t("auth.noAccount")} ${t("auth.signUpLink")}`}
                  styleClasses="z-50"
                >
                  <Button
                    className="h-11 w-full overflow-hidden rounded-lg"
                    variant="outline"
                    type="button"
                  >
                    <span className="truncate">
                      {t("auth.noAccount")}&nbsp;<b>{t("auth.signUpLink")}</b>
                    </span>
                  </Button>
                </ShadTooltip>
              </CustomLink>
            </div>
          </section>
        </div>
      </main>
    </Form.Root>
  );
}
