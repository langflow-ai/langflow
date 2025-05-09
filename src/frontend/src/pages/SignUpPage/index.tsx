import LangflowLogo from "@/assets/LangflowLogo.png?react";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { useAddUser } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import * as Form from "@radix-ui/react-form";
import { FormEvent, useEffect, useState } from "react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { SIGNUP_ERROR_ALERT } from "../../constants/alerts_constants";
import {
  CONTROL_INPUT_STATE,
  SIGN_UP_SUCCESS,
} from "../../constants/constants";
import useAlertStore from "../../stores/alertStore";
import {
  UserInputType,
  inputHandlerEventType,
  signUpInputStateType,
} from "../../types/components";

export default function SignUp(): JSX.Element {
  const [inputState, setInputState] =
    useState<signUpInputStateType>(CONTROL_INPUT_STATE);

  const [isDisabled, setDisableBtn] = useState<boolean>(true);

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

  useEffect(() => {
    if (password !== cnfPassword) return setDisableBtn(true);
    if (password === "" || cnfPassword === "") return setDisableBtn(true);
    if (username === "") return setDisableBtn(true);
    setDisableBtn(false);
  }, [password, cnfPassword, username, handleInput]);

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
          title: SIGN_UP_SUCCESS,
        });
        navigate("/login");
      },
      onError: (error) => {
        const {
          response: {
            data: { detail },
          },
        } = error;
        setErrorData({
          title: SIGNUP_ERROR_ALERT,
          list: [detail],
        });
      },
    });
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#f5f7fa] to-[#c3cfe2]">
      <Form.Root
        onSubmit={(event: FormEvent<HTMLFormElement>) => {
          if (password === "") {
            event.preventDefault();
            return;
          }
          const data = Object.fromEntries(new FormData(event.currentTarget));
          event.preventDefault();
        }}
        className="w-full max-w-md"
      >
        <div className="bg-white rounded-2xl shadow-xl px-8 py-10 flex flex-col items-center w-full">
          <div className="flex flex-col items-center mb-6">
            <img src={LangflowLogo} alt="Langflow Logo" className="h-16 w-16 mb-4 rounded-full object-contain" />
            <h2 className="text-2xl font-semibold text-gray-900 mb-1">Sign up for Sochflow</h2>
            <p className="text-gray-500 text-sm">Create your account to get started</p>
          </div>
          <div className="w-full mb-4">
            <Form.Field name="username">
              <Form.Label className="block mb-1 text-gray-700 font-medium">
                Email
              </Form.Label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">
                  <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25H4.5a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-.977 1.872l-7.5 5.25a2.25 2.25 0 01-2.546 0l-7.5-5.25A2.25 2.25 0 012.25 6.993V6.75"/></svg>
                </span>
                <Input
                  type="email"
                  onChange={({ target: { value } }) => {
                    handleInput({ target: { name: "username", value } });
                  }}
                  value={username}
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  required
                  placeholder="Email"
                />
              </div>
              <Form.Message match="valueMissing" className="text-xs text-red-500 mt-1">
                Please enter your email
              </Form.Message>
            </Form.Field>
          </div>
          <div className="w-full mb-2">
            <Form.Field name="password" serverInvalid={password != cnfPassword}>
              <Form.Label className="block mb-1 text-gray-700 font-medium">
                Password
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
                className="w-full pr-10 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400"
                leftIcon={
                  <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                    <rect x="5" y="11" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
                    <path d="M8 11V8a4 4 0 1 1 8 0v3" stroke="currentColor" strokeWidth="1.5" />
                    <circle cx="12" cy="15" r="1" fill="currentColor" />
                  </svg>
                }
              />
              <Form.Message className="text-xs text-red-500 mt-1" match="valueMissing">
                Please enter a password
              </Form.Message>
              {password != cnfPassword && (
                <Form.Message className="text-xs text-red-500 mt-1">
                  Passwords do not match
                </Form.Message>
              )}
            </Form.Field>
          </div>
          <div className="w-full mb-4">
            <Form.Field name="confirmpassword" serverInvalid={password != cnfPassword}>
              <Form.Label className="block mb-1 text-gray-700 font-medium">
                Confirm your password
              </Form.Label>
              <InputComponent
                onChange={(value) => {
                  handleInput({ target: { name: "cnfPassword", value } });
                }}
                value={cnfPassword}
                isForm
                password={true}
                required
                placeholder="Confirm your password"
                className="w-full pr-10 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400"
                leftIcon={
                  <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                    <rect x="5" y="11" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
                    <path d="M8 11V8a4 4 0 1 1 8 0v3" stroke="currentColor" strokeWidth="1.5" />
                    <circle cx="12" cy="15" r="1" fill="currentColor" />
                  </svg>
                }
              />
              <Form.Message className="text-xs text-red-500 mt-1" match="valueMissing">
                Please confirm your password
              </Form.Message>
            </Form.Field>
          </div>
          <div className="w-full">
            <Form.Submit asChild>
              <Button
                disabled={isDisabled}
                type="submit"
                className="w-full bg-gradient-to-r from-indigo-500 to-purple-500 text-white font-semibold py-2 rounded-lg shadow-md hover:from-indigo-600 hover:to-purple-600 transition-colors mt-6"
                onClick={() => {
                  handleSignup();
                }}
              >
                Sign up
              </Button>
            </Form.Submit>
          </div>
          <div className="flex items-center w-full my-3">
            <div className="flex-grow h-px bg-gray-200" />
            <span className="mx-3 text-gray-400 text-sm">or continue with</span>
            <div className="flex-grow h-px bg-gray-200" />
          </div>
          <div className="flex w-full gap-3 mb-4">
            <Button variant="outline" className="w-1/2 flex items-center justify-center gap-2 border-gray-300">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 2C6.477 2 2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.877v-6.987h-2.54v-2.89h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.242 0-1.632.771-1.632 1.562v1.875h2.773l-.443 2.89h-2.33v6.987C18.343 21.128 22 16.991 22 12c0-5.523-4.477-10-10-10z" fill="#1877F2"/></svg>
              GitHub
            </Button>
            <Button variant="outline" className="w-1/2 flex items-center justify-center gap-2 border-gray-300">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M21.805 10.023h-9.18v3.954h5.25c-.225 1.2-.9 2.22-1.92 2.892v2.4h3.105c1.815-1.668 2.745-4.125 2.745-6.846 0-.45-.045-.885-.09-1.305z" fill="#4285F4"/><path d="M12.625 21c2.475 0 4.545-.825 6.06-2.25l-3.105-2.4c-.855.57-1.95.915-2.955.915-2.28 0-4.215-1.545-4.905-3.63H4.49v2.28C6 19.095 9.045 21 12.625 21z" fill="#34A853"/><path d="M7.72 13.635a5.89 5.89 0 010-3.78v-2.28H4.49a8.98 8.98 0 000 8.34l3.23-2.28z" fill="#FBBC05"/><path d="M12.625 7.425c1.35 0 2.565.465 3.525 1.38l2.64-2.565C17.165 4.92 15.095 4.05 12.625 4.05c-3.58 0-6.625 1.905-8.135 4.695l3.23 2.28c.69-2.085 2.625-3.6 4.905-3.6z" fill="#EA4335"/></svg>
              Google
            </Button>
          </div>
          <div className="w-full mt-4">
            <CustomLink to="/login">
              <Button className="w-full" variant="outline">
                Already have an account? <b>Sign in</b>
              </Button>
            </CustomLink>
          </div>
        </div>
      </Form.Root>
    </div>
  );
}
