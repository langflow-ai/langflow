import * as Form from "@radix-ui/react-form";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { extractApiErrorMessage } from "@/controllers/API/helpers/extract-api-error-message";
import { useAddUser } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useTheme from "@/customization/hooks/use-custom-theme";
import { track } from "@/customization/utils/analytics";
import { useDocumentTitle } from "@/hooks/use-document-title";
import {
  appendErrorSuggestion,
  getRequiredFieldError,
} from "@/utils/authErrorMessages";
import { Button, buttonVariants } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { CONTROL_INPUT_STATE } from "../../constants/constants";
import useAlertStore from "../../stores/alertStore";
import type {
  inputHandlerEventType,
  signUpInputStateType,
  UserInputType,
} from "../../types/components";
import { cn } from "../../utils/utils";
import DotGridBackground from "../LoginPage/components/dot-grid-background";

export default function SignUp(): JSX.Element {
  const [inputState, setInputState] =
    useState<signUpInputStateType>(CONTROL_INPUT_STATE);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [confirmPasswordTouched, setConfirmPasswordTouched] = useState(false);
  // Server-side rejection (e.g. username taken), mirrored inline so the error
  // is programmatically associated with the username field (WCAG 3.3.1)
  // instead of living only in the transient toast.
  const [serverError, setServerError] = useState<string | null>(null);

  const { t } = useTranslation();
  useDocumentTitle(t("auth.signupButton"));
  useTheme();
  const { password, cnfPassword, username } = inputState;
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const navigate = useCustomNavigate();

  const { mutate: mutateAddUser } = useAddUser();

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
    setServerError(null);
  }

  function handleSignup(): void {
    const { username, password } = inputState;
    const newUser: UserInputType = {
      username: username.trim(),
      password: password.trim(),
    };

    mutateAddUser(newUser, {
      onSuccess: (user) => {
        track("User Signed Up", user);
        setSuccessData({
          title: t("auth.signUpSuccess"),
        });
        navigate("/login");
      },
      onError: (error) => {
        const message = appendErrorSuggestion(
          extractApiErrorMessage(
            error as Parameters<typeof extractApiErrorMessage>[0],
            t("errors.signup"),
          ),
          t("errors.signupSuggestion", {
            defaultValue:
              "Use a different username or contact an administrator if you already have an account.",
          }),
        );
        setServerError(message);
        setErrorData({
          title: t("errors.signup"),
          list: [message],
        });
      },
    });
  }

  const passwordMismatch =
    password !== "" && cnfPassword !== "" && password !== cnfPassword;
  const usernameError = getRequiredFieldError(
    submitAttempted,
    username,
    t("auth.usernameRequired"),
  );
  const passwordError = getRequiredFieldError(
    submitAttempted,
    password,
    t("auth.passwordEnterRequired"),
  );
  const shouldShowPasswordMismatch =
    passwordMismatch && (submitAttempted || confirmPasswordTouched);
  const confirmPasswordRequiredError = getRequiredFieldError(
    submitAttempted,
    cnfPassword,
    t("auth.confirmPasswordRequired"),
  );
  const confirmPasswordError =
    confirmPasswordRequiredError ??
    (shouldShowPasswordMismatch
      ? `${t("errors.passwordMismatch")}. ${t(
          "errors.passwordMismatchSuggestion",
          {
            defaultValue: "Re-enter both passwords so they match.",
          },
        )}`
      : undefined);

  return (
    <Form.Root
      onInvalidCapture={() => setSubmitAttempted(true)}
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        setSubmitAttempted(true);
        if (
          username.trim() === "" ||
          password.trim() === "" ||
          cnfPassword.trim() === "" ||
          passwordMismatch
        ) {
          event.preventDefault();
          return;
        }

        event.preventDefault();
        handleSignup();
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
            <h1 className="pl-2 text-center text-4xl font-semibold tracking-tight">
              {t("auth.signupTitle")}
            </h1>
          </div>

          <section className="w-full rounded-xl border border-border bg-card p-8 shadow-2xl shadow-black/10 dark:shadow-black/40 sm:p-10">
            <div className="flex flex-col gap-6">
              <Form.Field name="username" className="pb-3">
                <label
                  htmlFor="signup-username"
                  className={`mb-2 flex items-center gap-1 overflow-hidden text-sm font-medium ${
                    usernameError ? "label-invalid" : ""
                  }`}
                >
                  <ShadTooltip
                    content={t("auth.usernameLabel")}
                    styleClasses="z-50"
                  >
                    <span className="truncate">{t("auth.usernameLabel")}</span>
                  </ShadTooltip>
                  <span className="shrink-0 font-medium text-destructive">
                    *
                  </span>
                </label>

                <Input
                  id="signup-username"
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
                      usernameError && "signup-username-error",
                      serverError && "signup-form-error",
                    ]
                      .filter(Boolean)
                      .join(" ") || undefined
                  }
                  aria-invalid={Boolean(usernameError || serverError)}
                  placeholder={t("auth.usernamePlaceholder")}
                />

                {usernameError && (
                  <p
                    id="signup-username-error"
                    role="alert"
                    className="field-invalid"
                  >
                    {usernameError}
                  </p>
                )}
              </Form.Field>

              <Form.Field
                name="password"
                serverInvalid={Boolean(passwordError)}
                className="pb-3"
              >
                <label
                  htmlFor="form-signup-password"
                  className={`mb-2 flex items-center gap-1 overflow-hidden text-sm font-medium ${
                    passwordError ? "label-invalid" : ""
                  }`}
                >
                  <ShadTooltip
                    content={t("auth.passwordLabel")}
                    styleClasses="z-50"
                  >
                    <span className="truncate">{t("auth.passwordLabel")}</span>
                  </ShadTooltip>
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
                  id="signup-password"
                  inputProps={{
                    autoComplete: "new-password",
                    "aria-describedby": passwordError
                      ? "signup-password-error"
                      : undefined,
                    "aria-invalid": Boolean(passwordError) || undefined,
                  }}
                  placeholder={t("auth.passwordPlaceholder")}
                  className="h-11 w-full rounded-lg bg-muted"
                />

                {passwordError && (
                  <p
                    id="signup-password-error"
                    role="alert"
                    className="field-invalid"
                  >
                    {passwordError}
                  </p>
                )}
              </Form.Field>

              <Form.Field
                name="confirmpassword"
                serverInvalid={Boolean(confirmPasswordError)}
                className="pb-3"
              >
                <label
                  htmlFor="form-signup-confirm-password"
                  className={`mb-2 flex items-center gap-1 overflow-hidden text-sm font-medium ${
                    confirmPasswordError ? "label-invalid" : ""
                  }`}
                >
                  <ShadTooltip
                    content={t("auth.confirmPasswordLabel")}
                    styleClasses="z-50"
                  >
                    <span className="truncate">
                      {t("auth.confirmPasswordLabel")}
                    </span>
                  </ShadTooltip>
                  <span className="shrink-0 font-medium text-destructive">
                    *
                  </span>
                </label>

                <InputComponent
                  onChange={(value) => {
                    handleInput({ target: { name: "cnfPassword", value } });
                  }}
                  onBlur={() => setConfirmPasswordTouched(true)}
                  value={cnfPassword}
                  isForm
                  allowAutofill
                  password={true}
                  required
                  id="signup-confirm-password"
                  inputProps={{
                    autoComplete: "new-password",
                    "aria-describedby": confirmPasswordError
                      ? "signup-confirm-password-error"
                      : undefined,
                    "aria-invalid": Boolean(confirmPasswordError) || undefined,
                  }}
                  placeholder={t("auth.confirmPasswordPlaceholder")}
                  className="h-11 w-full rounded-lg bg-muted"
                />

                {confirmPasswordError && (
                  <p
                    id="signup-confirm-password-error"
                    role="alert"
                    className="field-invalid"
                  >
                    {confirmPasswordError}
                  </p>
                )}
              </Form.Field>

              {serverError && (
                <p
                  id="signup-form-error"
                  role="alert"
                  className="field-invalid static"
                >
                  {serverError}
                </p>
              )}

              <Form.Submit asChild>
                <Button type="submit" className="h-11 w-full rounded-lg">
                  {t("auth.signupButton")}
                </Button>
              </Form.Submit>

              <ShadTooltip content={t("auth.signInPrompt")} styleClasses="z-50">
                <CustomLink
                  className={cn(
                    buttonVariants({ variant: "outline" }),
                    "h-11 w-full overflow-hidden rounded-lg",
                  )}
                  to="/login"
                >
                  <span className="truncate">{t("auth.signInPrompt")}</span>
                </CustomLink>
              </ShadTooltip>
            </div>
          </section>
        </div>
      </main>
    </Form.Root>
  );
}
