import LangflowLogo from "@/assets/LangflowLogo.svg?react";
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
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [passwordStrength, setPasswordStrength] = useState<{
    score: number;
    feedback: any[];
  }>({ score: 0, feedback: [] });

  const { password, cnfPassword, username } = inputState;
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const navigate = useCustomNavigate();

  const { mutate: mutateAddUser } = useAddUser();

  const isFormValid = () => {
    return (
      username.trim() !== "" &&
      password.trim() !== "" &&
      password === cnfPassword &&
      password.length >= 8
    );
  };

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
    
    // Clear form error when input changes
    if (formError) {
      setFormError(null);
    }
    
    // Analyze password strength when password changes
    if (name === "password") {
      analyzePasswordStrength(typeof value === 'string' ? value : '');
    }
  }

  function analyzePasswordStrength(password: string): void {
    if (!password) {
      setPasswordStrength({ score: 0, feedback: [] });
      return;
    }

    // Simple password strength criteria
    const criteria = [
      { test: password.length >= 8, message: "Minimum 8 characters" },
      { test: /[A-Z]/.test(password), message: "At least 1 uppercase letter" },
      { test: /[a-z]/.test(password), message: "At least 1 lowercase letter" },
      { test: /[0-9]/.test(password), message: "At least 1 number" },
      { test: /[^A-Za-z0-9]/.test(password), message: "At least 1 special character" }
    ];

    // Count passed criteria
    const passedCriteria = criteria.filter(c => c.test);
    const score = passedCriteria.length;
    
    // Create feedback for missing criteria
    const feedback = criteria.map(c => ({ 
      message: c.message, 
      passed: c.test 
    }));

    setPasswordStrength({ score, feedback });
  }

  function handleSignup(event: FormEvent): void {
    event.preventDefault();
    
    // Form validation
    if (!username.trim()) {
      setFormError("Please enter a username");
      return;
    }
    
    if (!password.trim()) {
      setFormError("Please enter a password");
      return;
    }
    
    if (password.length < 8) {
      setFormError("Password must be at least 8 characters");
      return;
    }
    
    if (password !== cnfPassword) {
      setFormError("Passwords do not match");
      return;
    }
    
    setIsLoading(true);
    
    const newUser: UserInputType = {
      username: username.trim(),
      password: password.trim(),
    };

    mutateAddUser(newUser, {
      onSuccess: (user) => {
        try {
          track("User Signed Up", user);
        } catch (e) {
          console.error("Error tracking signup:", e);
        }
        
        setSuccessData({
          title: SIGN_UP_SUCCESS,
        });
        navigate("/login");
      },
      onError: (error) => {
        try {
          const errorMessage = error?.response?.data?.detail || "Registration failed, please try again";
          setErrorData({
            title: SIGNUP_ERROR_ALERT,
            list: [errorMessage],
          });
          setFormError(errorMessage);
        } catch (e) {
          setFormError("An error occurred during registration, please try again later");
        }
      },
      onSettled: () => {
        setIsLoading(false);
      }
    });
  }

  // Get color for password strength indicator
  const getPasswordStrengthColor = () => {
    const { score } = passwordStrength;
    if (score <= 1) return "bg-destructive";
    if (score <= 3) return "bg-yellow-500";
    return "bg-green-500";
  };

  // Get text description for password strength
  const getPasswordStrengthText = () => {
    const { score } = passwordStrength;
    if (score <= 1) return "Weak";
    if (score <= 3) return "Medium";
    return "Strong";
  };

  return (
    <Form.Root
      onSubmit={handleSignup}
      className="h-screen w-full"
    >
      <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
        <div className="flex w-80 flex-col items-center justify-center gap-2 bg-background p-8 rounded-lg shadow-sm">
          <LangflowLogo
            title="Logo"
            className="mb-4 h-10 w-10 scale-[1.5]"
          />
          <span className="mb-6 text-2xl font-semibold text-primary">
            Sign up
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
            <Form.Field name="password" serverInvalid={password !== cnfPassword}>
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
                id="signup-password-input"
              />

              {password && (
                <div className="mt-2">
                  <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                    <div 
                      className={`h-full ${getPasswordStrengthColor()}`} 
                      style={{ width: `${(passwordStrength.score / 5) * 100}%` }}
                    ></div>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Password strength: {getPasswordStrengthText()}
                  </div>
                  
                  <div className="mt-2 text-xs">
                    <ul className="space-y-1">
                      {passwordStrength.feedback.map((item, index) => (
                        <li 
                          key={index} 
                          className={`flex items-center ${item.passed ? 'text-green-500' : 'text-muted-foreground'}`}
                        >
                          <svg 
                            xmlns="http://www.w3.org/2000/svg" 
                            viewBox="0 0 20 20" 
                            fill="currentColor" 
                            className="w-3 h-3 mr-1.5 inline-block"
                          >
                            {item.passed ? (
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            ) : (
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v2H7a1 1 0 100 2h2v2a1 1 0 102 0v-2h2a1 1 0 100-2h-2V7z" clipRule="evenodd" />
                            )}
                          </svg>
                          {item.message}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              <Form.Message className="field-invalid mt-1" match="valueMissing">
                Please enter a password
              </Form.Message>
            </Form.Field>
          </div>
          
          <div className="mb-2 w-full">
            <Form.Field
              name="confirmpassword"
              serverInvalid={password !== cnfPassword && cnfPassword !== ""}
            >
              <Form.Label className="text-sm font-medium mb-1.5 block data-[invalid]:label-invalid">
                Confirm password <span className="font-medium text-destructive">*</span>
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
                className="w-full"
                disabled={isLoading}
                id="signup-confirm-password-input"
              />

              {password !== cnfPassword && cnfPassword !== "" && (
                <p className="field-invalid mt-1">
                  Passwords do not match
                </p>
              )}

              <Form.Message className="field-invalid mt-1" match="valueMissing">
                Please confirm your password
              </Form.Message>
            </Form.Field>
          </div>
          
          <div className="w-full">
            <Form.Submit asChild>
              <Button 
                type="submit" 
                className="mt-4 w-full" 
                disabled={!isFormValid() || isLoading}
              >
                {isLoading ? (
                  <div className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Signing up...
                  </div>
                ) : "Sign up"}
              </Button>
            </Form.Submit>
          </div>
          
          <div className="w-full mt-3">
            <CustomLink to="/login">
              <Button className="w-full" variant="outline" disabled={isLoading}>
                Already have an account?&nbsp;<span className="font-semibold">Sign in</span>
              </Button>
            </CustomLink>
          </div>
        </div>
      </div>
    </Form.Root>
  );
}