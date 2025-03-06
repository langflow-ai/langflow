import LangflowLogo from "@/assets/LangflowLogo.svg?react";
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

export default function LoginPage(): JSX.Element {
  const [inputState, setInputState] =
    useState<loginInputStateType>(CONTROL_LOGIN_STATE);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { password, username } = inputState;
  const { login } = useContext(AuthContext);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
    
    // Clear form error when input changes
    if (formError) {
      setFormError(null);
    }
  }

  const { mutate } = useLoginUser();

  function signIn(event: React.FormEvent) {
    event.preventDefault();
    
    // Basic form validation
    if (!username.trim()) {
      setFormError("Please enter your username");
      return;
    }
    
    if (!password.trim()) {
      setFormError("Please enter your password");
      return;
    }
    
    setIsLoading(true);
    
    const user: LoginType = {
      username: username.trim(),
      password: password.trim(),
    };

    mutate(user, {
      onSuccess: (data) => {
        login(data.access_token, "login", data.refresh_token);
      },
      onError: (error) => {
        try {
          const errorMessage = error?.response?.data?.detail || "Login failed, please try again";
          setErrorData({
            title: SIGNIN_ERROR_ALERT,
            list: [errorMessage],
          });
          setFormError(errorMessage);
        } catch (e) {
          setFormError("An error occurred during login, please try again later");
        }
      },
      onSettled: () => {
        setIsLoading(false);
      }
    });
  }

  return (
    <Form.Root
      onSubmit={signIn}
      className="h-screen w-full"
    >
      <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
        <div className="flex w-80 flex-col items-center justify-center gap-2 bg-background p-8 rounded-lg shadow-sm">
          <LangflowLogo
            title="logo"
            className="mb-4 h-10 w-10 scale-[1.5]"
          />
          <span className="mb-6 text-2xl font-semibold text-primary">
            Sign in
          </span>
          
          {formError && (
            <div className="w-full mb-4 p-3 text-sm bg-destructive/10 border border-destructive/20 text-destructive rounded-md">
              {formError}
            </div>
          )}
          
          <div className="mb-4 w-full">
            <Form.Field name="username">
              <Form.Label className="text-sm font-medium mb-1.5 block data-[invalid]:label-invalid">
                Username <span className="font-medium text-destructive">*</span>
              </Form.Label>

              <Form.Control asChild>
                <Input
                  type="text"
                  onChange={({ target: { value } }) => {
                    handleInput({ target: { name: "username", value } });
                  }}
                  value={username}
                  className="w-full"
                  required
                  placeholder="Enter your username"
                  disabled={isLoading}
                />
              </Form.Control>

              <Form.Message match="valueMissing" className="field-invalid mt-1">
                Please enter your username
              </Form.Message>
            </Form.Field>
          </div>
          
          <div className="mb-4 w-full">
            <Form.Field name="password">
              <Form.Label className="text-sm font-medium mb-1.5 block data-[invalid]:label-invalid">
                Password <span className="font-medium text-destructive">*</span>
              </Form.Label>

              <InputComponent
                onChange={(value) => {
                  handleInput({ target: { name: "password", value } });
                }}
                value={password}
                isForm
                password={true}
                required
                placeholder="Enter your password"
                className="w-full"
                disabled={isLoading}
              />

              <Form.Message className="field-invalid mt-1" match="valueMissing">
                Please enter your password
              </Form.Message>
            </Form.Field>
          </div>
          
          <div className="w-full">
            <Form.Submit asChild>
              <Button 
                className="mt-2 w-full" 
                type="submit" 
                disabled={isLoading}
              >
                {isLoading ? (
                  <div className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Signing in...
                  </div>
                ) : "Sign in"}
              </Button>
            </Form.Submit>
          </div>
          
          <div className="w-full mt-3">
            <CustomLink to="/signup">
              <Button className="w-full" variant="outline" type="button" disabled={isLoading}>
                Don't have an account?&nbsp;<span className="font-semibold">Sign up</span>
              </Button>
            </CustomLink>
          </div>
        </div>
      </div>
    </Form.Root>
  );
}