import * as Form from "@radix-ui/react-form";
import { FormEvent, useState } from "react";
import InputComponent from "../../components/inputComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { CONTROL_INPUT_STATE } from "../../constants/constants";
import { inputHandlerEventType, signUpInputStateType } from "../../types/components";
import { Link } from "react-router-dom";
import IconComponent from "../../components/genericIconComponent";

export default function SignUp(): JSX.Element {
  const [inputState, setInputState] =
    useState<signUpInputStateType>(CONTROL_INPUT_STATE);

  const { password, cnfPassword, username } = inputState;

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }
  return (
    <Form.Root
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
          if (password === "") {
          event.preventDefault();
          return;
        }

        const data = Object.fromEntries(new FormData(event.currentTarget));
        event.preventDefault();
      }}
      className="w-full h-full"
    >
      <div className="flex h-full w-full flex-col items-center justify-center bg-muted">
        <div className="flex w-72 flex-col items-center justify-center gap-2">
          <span className="mb-4 text-5xl">⛓️</span>
          <span className="mb-6 text-2xl font-semibold text-primary">
            Sign up to LangFlow
          </span>
          <div className="flex w-full items-center justify-center gap-2">
            <Button variant="primary" className="w-full py-6">
              <IconComponent
                name="FaApple"
                className="h-6 w-6"
              />
            </Button>
            <Button variant="primary" className="w-full py-6">
              <IconComponent
                name="FaGithub"
                className="h-6 w-6"
              />
            </Button>
            <Button variant="primary" className="w-full py-6">
              <IconComponent
                name="GoogleSearchRun"
                className="h-6 w-6"
              />
            </Button>
          </div>
          <span className="text-sm text-muted-foreground">or</span>
          <div className="w-full mb-3">
            <Form.Field name="username">
              <Form.Label className="data-[invalid]:label-invalid">
                Username <span className="font-medium text-destructive">*</span>
              </Form.Label>

              <Form.Control asChild>
                <Input
                  onChange={({ target: { value } }) => {
                    handleInput({ target: { name: "username", value } });
                  }}
                  value={username}
                  className="w-full"
                  required
                  placeholder="Username"
                />
              </Form.Control>

              <Form.Message match="valueMissing" className="field-invalid">
                Please enter your username
              </Form.Message>
            </Form.Field>
          </div>
          <div className="w-full mb-3">
            <Form.Field name="password" serverInvalid={password != cnfPassword}>
              <Form.Label className="data-[invalid]:label-invalid">
                Password <span className="font-medium text-destructive">*</span>
              </Form.Label>

              <Form.Control asChild>
                <InputComponent
                  onChange={(value) => {
                    handleInput({ target: { name: "password", value } });
                  }}
                  value={password}
                  password={true}
                  placeholder="Password"
                  className="w-full"
                />
              </Form.Control>

              <Form.Message className="field-invalid" match="valueMissing">
                Please enter a password
              </Form.Message>

              {password != cnfPassword && (
                <Form.Message className="field-invalid">
                  Passwords do not match
                </Form.Message>
              )}
            </Form.Field>
          </div>
          <div className="w-full">
            <Form.Field
              name="confirmpassword"
              serverInvalid={password != cnfPassword}
            >
              <Form.Label className="data-[invalid]:label-invalid">
                Confirm your password{" "}
                <span className="font-medium text-destructive">*</span>
              </Form.Label>

              <Form.Control asChild>
                <InputComponent
                  onChange={(value) => {
                    handleInput({ target: { name: "cnfPassword", value } });
                  }}
                  value={cnfPassword}
                  password={true}
                />
              </Form.Control>

              <Form.Message className="field-invalid" match="valueMissing">
                Please confirm your password
              </Form.Message>
            </Form.Field>
          </div>
          <div className="w-full">
            <Form.Submit asChild>
              <Button className="mr-3 mt-6 w-full">Sign up</Button>
            </Form.Submit>
          </div>
          <div className="w-full">
            <Link to="/login">
              <Button className="w-full" variant="outline">
                Already have an account?&nbsp;<b>Sign in</b>
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </Form.Root>
  );
}
