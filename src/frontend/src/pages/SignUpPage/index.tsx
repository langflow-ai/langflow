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
import { track } from "@/customization/utils/analytics";
import {
  appendErrorSuggestion,
  getRequiredFieldError,
} from "@/utils/authErrorMessages";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { CONTROL_INPUT_STATE } from "../../constants/constants";
import useAlertStore from "../../stores/alertStore";
import type {
  inputHandlerEventType,
  signUpInputStateType,
  UserInputType,
} from "../../types/components";

export default function SignUp(): JSX.Element {
  const [inputState, setInputState] =
    useState<signUpInputStateType>(CONTROL_INPUT_STATE);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [confirmPasswordTouched, setConfirmPasswordTouched] = useState(false);

  const { t } = useTranslation();
  const { password, cnfPassword, username } = inputState;
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const navigate = useCustomNavigate();

  const { mutate: mutateAddUser } = useAddUser();

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
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
        setErrorData({
          title: t("errors.signup"),
          list: [
            appendErrorSuggestion(
              extractApiErrorMessage(
                error as Parameters<typeof extractApiErrorMessage>[0],
                t("errors.signup"),
              ),
              t("errors.signupSuggestion", {
                defaultValue:
                  "Use a different username or contact an administrator if you already have an account.",
              }),
            ),
          ],
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
      className="h-screen w-full"
    >
      <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
        <div className="flex w-full max-w-xs flex-col items-center justify-center gap-2">
          <LangflowLogo
            title={t("common.langflowLogo")}
            className="mb-4 h-10 w-10 scale-[1.5]"
          />
          <span className="mb-6 text-2xl font-semibold text-primary text-center">
            {t("auth.signupTitle")}
          </span>
          <div className="mb-3 w-full">
            <Form.Field name="username">
              <label
                htmlFor="signup-username"
                className={`flex items-center gap-1 overflow-hidden ${
                  usernameError ? "label-invalid" : ""
                }`}
              >
                <ShadTooltip
                  content={t("auth.usernameLabel")}
                  styleClasses="z-50"
                >
                  <span className="truncate">{t("auth.usernameLabel")}</span>
                </ShadTooltip>
                <span className="shrink-0 font-medium text-destructive">*</span>
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
                className="w-full"
                required
                aria-describedby={
                  usernameError ? "signup-username-error" : undefined
                }
                aria-invalid={Boolean(usernameError)}
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
          </div>
          <div className="mb-3 w-full">
            <Form.Field name="password" serverInvalid={Boolean(passwordError)}>
              <label
                htmlFor="form-signup-password"
                className={`flex items-center gap-1 overflow-hidden ${
                  passwordError ? "label-invalid" : ""
                }`}
              >
                <ShadTooltip
                  content={t("auth.passwordLabel")}
                  styleClasses="z-50"
                >
                  <span className="truncate">{t("auth.passwordLabel")}</span>
                </ShadTooltip>
                <span className="shrink-0 font-medium text-destructive">*</span>
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
                  "aria-describedby": passwordError
                    ? "signup-password-error"
                    : undefined,
                  "aria-invalid": Boolean(passwordError) || undefined,
                }}
                placeholder={t("auth.passwordPlaceholder")}
                className="w-full"
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
          </div>
          <div className="w-full">
            <Form.Field
              name="confirmpassword"
              serverInvalid={Boolean(confirmPasswordError)}
            >
              <label
                htmlFor="form-signup-confirm-password"
                className={`flex items-center gap-1 overflow-hidden ${
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
                <span className="shrink-0 font-medium text-destructive">*</span>
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
                  "aria-describedby": confirmPasswordError
                    ? "signup-confirm-password-error"
                    : undefined,
                  "aria-invalid": Boolean(confirmPasswordError) || undefined,
                }}
                placeholder={t("auth.confirmPasswordPlaceholder")}
                className="w-full"
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
          </div>
          <div className="w-full">
            <Form.Submit asChild>
              <Button type="submit" className="mr-3 mt-6 w-full">
                {t("auth.signupButton")}
              </Button>
            </Form.Submit>
          </div>
          <div className="w-full">
            <CustomLink to="/login">
              <ShadTooltip
                content={`${t("auth.haveAccount")} ${t("auth.signInLink")}`}
                styleClasses="z-50"
              >
                <Button className="w-full overflow-hidden" variant="outline">
                  <span className="truncate">
                    {t("auth.haveAccount")}&nbsp;<b>{t("auth.signInLink")}</b>
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
