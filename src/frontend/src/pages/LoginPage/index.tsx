import LangflowLogo from "@/assets/LangflowLogo.png?react";
import { useLoginUser } from "@/controllers/API/queries/auth";
import { CustomLink } from "@/customization/components/custom-link";
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

function validateEmail(email: string): boolean {
  // Simple email regex
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export default function LoginPage(): JSX.Element {
  const [inputState, setInputState] =
    useState<loginInputStateType>(CONTROL_LOGIN_STATE);
  const [touched, setTouched] = useState<{ username: boolean; password: boolean }>({ username: false, password: false });

  const { password, username } = inputState;
  const { login } = useContext(AuthContext);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
    setTouched((prev) => ({ ...prev, [name]: true }));
  }

  const { mutate } = useLoginUser();

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

  const isEmailValid = validateEmail(username);
  const isPasswordValid = password.trim().length > 0;
  const canSubmit = isEmailValid && isPasswordValid;

  return (
    <div className="min-h-screen flex items-center justify-center">
      <Form.Root
        onSubmit={(event) => {
          if (!canSubmit) {
            event.preventDefault();
            setTouched({ username: true, password: true });
            return;
          }
          signIn();
          const data = Object.fromEntries(new FormData(event.currentTarget));
          event.preventDefault();
        }}
        className="w-full max-w-md"
      >
        <div className="bg-white rounded-2xl shadow-xl px-8 py-10 flex flex-col items-center w-full">
          <div className="flex flex-col items-center mb-8 w-full">
            <div className="from-indigo-600 to-purple-500 p-[2px] rounded-full mb-3 shadow-lg">
              <div className="bg-white dark:bg-base-200 rounded-full flex items-center justify-center">
                <div className="avatar">
                  <div className="w-16 h-16 rounded-full ring from-indigo-600 to-purple-500 flex items-center justify-center">
                    <img src={LangflowLogo} alt="Sochflow Logo" className="object-contain w-12 h-12" />
                  </div>
                </div>
              </div>
            </div>
            <span className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-500 mb-1 tracking-tight drop-shadow-lg">Sochflow</span>
            <h2 className="text-xl font-bold text-gray-900 mb-1 mt-1 tracking-tight">Welcome Back</h2>
            <p className="text-gray-500 text-sm font-medium">Sign in to your Sochflow account</p>
          </div>
          <div className="w-full mb-4">
            <Form.Field name="username">
              <Form.Label className="block mb-1 text-gray-700 font-medium">
                Email
              </Form.Label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
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
                  onBlur={() => setTouched((prev) => ({ ...prev, username: true }))}
                />
              </div>
              {touched.username && !isEmailValid && (
                <div className="text-xs text-red-500 mt-1">Please enter a valid email address</div>
              )}
            </Form.Field>
          </div>
          <div className="w-full mb-2">
            <Form.Field name="password">
              <Form.Label className="block mb-1 text-gray-700 font-medium">
                Password
              </Form.Label>
              <div className="relative">
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
                  onBlur={() => setTouched((prev) => ({ ...prev, password: true }))}
                />
              </div>
              {touched.password && !isPasswordValid && (
                <div className="text-xs text-red-500 mt-1">Please enter your password</div>
              )}
            </Form.Field>
          </div>
          {/* <div className="flex items-center justify-between w-full mb-4">
            <label className="flex items-center text-sm text-gray-600">
              <input type="checkbox" className="form-checkbox mr-2" /> Remember me
            </label>
            <CustomLink to="/forgot-password" className="text-indigo-500 text-sm hover:underline">
              Forgot password?
            </CustomLink>
          </div> */}
          <div className="w-full mb-3 mt-3">
            <Form.Submit asChild>
              <Button
                className="w-full bg-gradient-to-r from-indigo-500 to-purple-500 text-white font-semibold py-2 rounded-lg shadow-md hover:from-indigo-600 hover:to-purple-600 transition-colors"
                type="submit"
                disabled={!canSubmit}
              >
                Sign In
              </Button>
            </Form.Submit>
          </div>
          {/* <div className="flex items-center w-full my-3">
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
          <div className="w-full">
            <CustomLink to="/signup">
              <Button className="w-full" variant="outline" type="button">
                Don't have an account? <b>Sign up</b>
              </Button>
            </CustomLink>
          </div> */}
        </div>
      </Form.Root>
    </div>
  );
}
