import * as Form from "@radix-ui/react-form";
import { useEffect, useState } from "react";
import { Button } from "../../components/ui/button";
import { UserManagementType } from "../../types/components";
import { nodeIconsLucide } from "../../utils/styleUtils";
import BaseModal from "../baseModal";
import InputComponent from "../../components/inputComponent";

export default function UserManagementModal({
  title,
  titleHeader,
  cancelText,
  confirmationText,
  children,
  icon,
  data,
  index,
  onConfirm,
}: UserManagementType) {
  const Icon: any = nodeIconsLucide[icon];

  const [open, setOpen] = useState(false);

  const [password, setPassword] = useState(data?.password ?? "");
  const [username, setUserName] = useState(data?.user ?? "");
  const [confirmPassword, setConfirmPassword] = useState(data?.password ?? "");

  useEffect(() => {
    if (!data) {
      resetForm();
    }
  }, [data, open]);

  function resetForm() {
    setPassword("");
    setUserName("");
    setConfirmPassword("");
  }

  return (
    <BaseModal size="medium-h-full" open={open} setOpen={setOpen}>
      <BaseModal.Trigger>{children}</BaseModal.Trigger>
      <BaseModal.Header description={titleHeader}>
        <span className="pr-2">{title}</span>
        <Icon
          name="icon"
          className="h-6 w-6 pl-1 text-foreground"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <Form.Root
          onSubmit={(event) => {
            if (password !== confirmPassword) {
              event.preventDefault();
              return;
            }

            const data = Object.fromEntries(new FormData(event.currentTarget));
            resetForm();
            onConfirm(index ?? -1, data);
            setOpen(false);
            event.preventDefault();
          }}
        >
          <div className="grid gap-5">
            <Form.Field name="username">
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  justifyContent: "space-between",
                }}
              >
                <Form.Label className="data-[invalid]:label-invalid">
                  Username{" "}
                  <span className="font-medium text-destructive">*</span>
                </Form.Label>
              </div>
              <Form.Control asChild>
                <input
                  onChange={(input) => {
                    setUserName(input.target.value);
                  }}
                  value={username}
                  className="primary-input"
                  required
                  placeholder="Username"
                />
              </Form.Control>
              <Form.Message match="valueMissing" className="field-invalid">
                Please enter your username
              </Form.Message>
            </Form.Field>

            <div className="flex flex-row">
              <div className="mr-3 basis-1/2">
                <Form.Field
                  name="password"
                  serverInvalid={password != confirmPassword}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      justifyContent: "space-between",
                    }}
                  >
                    <Form.Label className="data-[invalid]:label-invalid">
                      Password{" "}
                      <span className="font-medium text-destructive">*</span>
                    </Form.Label>
                  </div>
                  <InputComponent
                    onChange={(input) => {
                      setPassword(input);
                    }}
                    value={password}
                    password={true}
                    isForm
                    className="primary-input"
                    required
                    placeholder="Password"
                  />
                  <Form.Message className="field-invalid" match="valueMissing">
                    Please enter a password
                  </Form.Message>

                  {password != confirmPassword && (
                    <Form.Message className="field-invalid">
                      Passwords do not match
                    </Form.Message>
                  )}
                </Form.Field>
              </div>

              <div className="basis-1/2">
                <Form.Field
                  name="confirmpassword"
                  serverInvalid={password != confirmPassword}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      justifyContent: "space-between",
                    }}
                  >
                    <Form.Label className="data-[invalid]:label-invalid">
                      Confirm password{" "}
                      <span className="font-medium text-destructive">*</span>
                    </Form.Label>
                  </div>
                  <InputComponent
                    onChange={(input) => {
                      setConfirmPassword(input);
                    }}
                    value={confirmPassword}
                    password={true}
                    isForm
                    className="primary-input"
                    required
                    placeholder="Confirm your password"
                  />
                  <Form.Message className="field-invalid" match="valueMissing">
                    Please confirm your password
                  </Form.Message>
                </Form.Field>
              </div>
            </div>

            {/* 
            <Form.Field name="email">
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  justifyContent: "space-between",
                }}
              >
                <Form.Label className="data-[invalid]:label-invalid">
                  Email <span className="font-medium text-destructive">*</span>
                </Form.Label>
                <Form.Message className="field-invalid" match="valueMissing">
                  Please enter your email
                </Form.Message>
                <Form.Message className="field-invalid" match="typeMismatch">
                  Please provide a valid email
                </Form.Message>
              </div>
              <Form.Control asChild>
                <input className="primary-input" type="email" required />
              </Form.Control>
            </Form.Field> */}

            {/* 
            <Form.Field name="birth">
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  justifyContent: "space-between",
                }}
              >
                <Form.Label className="data-[invalid]:label-invalid">
                  Date of birth{" "}
                  <span className="font-medium text-destructive">*</span>
                </Form.Label>
                <Form.Message className="field-invalid" match="valueMissing">
                  Please enter your date of birth
                </Form.Message>
              </div>
              <Form.Control asChild>
                <input
                  type="date"
                  className="primary-input"
                  required
                  max={new Date().toISOString().split("T")[0]}
                />
              </Form.Control>
            </Form.Field> */}
          </div>

          <div className="float-right">
            <Form.Submit asChild>
              <Button className="mr-3 mt-8">{confirmationText}</Button>
            </Form.Submit>
            <Button
              variant="outline"
              onClick={() => {
                setOpen(false);
              }}
            >
              {cancelText}
            </Button>
          </div>
        </Form.Root>
      </BaseModal.Content>
    </BaseModal>
  );
}
