import * as Form from "@radix-ui/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { useContext, useState } from "react";
import { useTranslation } from "react-i18next";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { extractApiErrorMessage } from "@/controllers/API/helpers/extract-api-error-message";
import { useLoginUser } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
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
      className="h-screen w-full"
    >
      <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
        <div className="flex w-full max-w-xs flex-col items-center justify-center gap-2">
          <LangflowLogo
            title={t("common.langflowLogo")}
            className="mb-4 h-10 w-10 scale-[1.5]"
          />
          <span className="mb-6 text-2xl font-semibold text-primary text-center">
            {t("auth.loginTitle")}
          </span>
          <div className="mb-3 w-full">
            <Form.Field name="username">
              <label
                htmlFor="login-username"
                className={`flex items-center gap-1 overflow-hidden ${
                  usernameError ? "label-invalid" : ""
                }`}
              >
                <span className="truncate">{t("auth.usernameLabel")}</span>
                <span className="shrink-0 font-medium text-destructive">*</span>
              </label>

              <Input
                id="login-username"
                name="username"
                type="text"
                autoComplete="username"
                onChange={({ target: { value } }) => {
                  handleInput({ target: { name: "username", value } });
                }}
                value={username}
                className="w-full"
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
          </div>
          <div className="mb-3 w-full">
            <Form.Field name="password">
              <label
                htmlFor="form-login-password"
                className={`flex items-center gap-1 overflow-hidden ${
                  passwordError ? "label-invalid" : ""
                }`}
              >
                <span className="truncate">{t("auth.passwordLabel")}</span>
                <span className="shrink-0 font-medium text-destructive">*</span>
              </label>

              <InputComponent
                onChange={(value) => {
                  handleInput({ target: { name: "password", value } });
                }}
                value={password}
                isForm
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
                className="w-full"
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
          </div>
          <div className="w-full">
            <Form.Submit asChild>
              <Button className="mr-3 mt-6 w-full" type="submit">
                {t("auth.signInButton")}
              </Button>
            </Form.Submit>
          </div>
          <div className="w-full">
            <CustomLink to="/signup">
              <ShadTooltip
                content={`${t("auth.noAccount")} ${t("auth.signUpLink")}`}
                styleClasses="z-50"
              >
                <Button
                  className="w-full overflow-hidden"
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
        </div>
      </div>
    </Form.Root>
  );
}
