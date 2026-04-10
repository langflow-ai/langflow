import * as Form from "@radix-ui/react-form";
import { useQueryClient } from "@tanstack/react-query";
import { useContext, useState } from "react";
import { useTranslation } from "react-i18next";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import {
  useLoginUser,
  usePostTotpVerifyLogin,
} from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
import { useSanitizeRedirectUrl } from "@/hooks/use-sanitize-redirect-url";
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
  const [partialToken, setPartialToken] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState("");

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
  const { mutate: mutateVerifyTotp, isPending: isTotpPending } =
    usePostTotpVerifyLogin();
  const queryClient = useQueryClient();

  function signIn() {
    const user: LoginType = {
      username: username.trim(),
      password: password.trim(),
    };

    mutate(user, {
      onSuccess: (data) => {
        if (data?.totp_required && data?.partial_token) {
          setPartialToken(data.partial_token);
          return;
        }
        clearAuthSession();
        login(data.access_token, "login", data.refresh_token);
        queryClient.clear();
      },
      onError: (error) => {
        setErrorData({
          title: t("errors.signin"),
          list: [error["response"]["data"]["detail"]],
        });
      },
    });
  }

  function submitTotpCode() {
    if (!partialToken) return;
    mutateVerifyTotp(
      { partial_token: partialToken, code: totpCode.trim() },
      {
        onSuccess: (data) => {
          clearAuthSession();
          login(data.access_token, "login", data.refresh_token);
          queryClient.clear();
        },
        onError: (error) => {
          setErrorData({
            title: t("errors.signin"),
            list: [error["response"]["data"]["detail"]],
          });
          setTotpCode("");
        },
      },
    );
  }

  if (partialToken !== null) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center bg-muted">
        <div className="flex w-72 flex-col items-center justify-center gap-2">
          <LangflowLogo
            title="Langflow logo"
            className="mb-4 h-10 w-10 scale-[1.5]"
          />
          <span className="mb-1 text-2xl font-semibold text-primary">
            {t("auth.loginTitle")}
          </span>
          <span className="mb-4 text-center text-sm text-muted-foreground">
            {t("auth.totpDescription")}
          </span>
          <div className="mb-3 w-full">
            <label className="mb-1 block text-center text-sm font-medium">
              {t("settings.totpCodeLabel")}
            </label>
            <Input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
              placeholder={t("settings.totpCodePlaceholder")}
              className="w-full text-center font-mono text-lg tracking-widest"
              placeholderClassName="left-0 w-full pl-0 text-center font-mono text-lg tracking-widest text-muted-foreground/40"
              autoComplete="one-time-code"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter" && totpCode.length === 6) {
                  submitTotpCode();
                }
              }}
            />
          </div>
          <div className="w-full">
            <Button
              className="w-full"
              type="button"
              disabled={totpCode.length < 6 || isTotpPending}
              onClick={submitTotpCode}
            >
              {t("auth.signInButton")}
            </Button>
          </div>
          <div className="w-full">
            <Button
              className="w-full"
              variant="outline"
              type="button"
              onClick={() => {
                setPartialToken(null);
                setTotpCode("");
              }}
            >
              {t("settings.totpCancelButton")}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <Form.Root
      onSubmit={(event) => {
        if (password === "") {
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
        <div className="flex w-72 flex-col items-center justify-center gap-2">
          <LangflowLogo
            title="Langflow logo"
            className="mb-4 h-10 w-10 scale-[1.5]"
          />
          <span className="mb-6 text-2xl font-semibold text-primary">
            {t("auth.loginTitle")}
          </span>
          <div className="mb-3 w-full">
            <Form.Field name="username">
              <Form.Label className="data-[invalid]:label-invalid">
                {t("auth.usernameLabel")}{" "}
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
                  placeholder={t("auth.usernamePlaceholder")}
                />
              </Form.Control>

              <Form.Message match="valueMissing" className="field-invalid">
                {t("auth.usernameRequired")}
              </Form.Message>
            </Form.Field>
          </div>
          <div className="mb-3 w-full">
            <Form.Field name="password">
              <Form.Label className="data-[invalid]:label-invalid">
                {t("auth.passwordLabel")}{" "}
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
                placeholder={t("auth.passwordPlaceholder")}
                className="w-full"
              />

              <Form.Message className="field-invalid" match="valueMissing">
                {t("auth.passwordRequired")}
              </Form.Message>
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
              <Button className="w-full" variant="outline" type="button">
                {t("auth.noAccount")}&nbsp;<b>{t("auth.signUpLink")}</b>
              </Button>
            </CustomLink>
          </div>
        </div>
      </div>
    </Form.Root>
  );
}
