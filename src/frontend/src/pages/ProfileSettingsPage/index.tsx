import * as Form from "@radix-ui/react-form";
import { useContext, useEffect, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import Header from "../../components/headerComponent";
import InputComponent from "../../components/inputComponent";
import { Button } from "../../components/ui/button";
import { CONTROL_PATCH_USER_STATE } from "../../constants/constants";
import { alertContext } from "../../contexts/alertContext";
import { AuthContext } from "../../contexts/authContext";
import { TabsContext } from "../../contexts/tabsContext";
import { updateUser } from "../../controllers/API";
import {
  inputHandlerEventType,
  patchUserInputStateType,
} from "../../types/components";
export default function ProfileSettingsPage(): JSX.Element {
  const { setTabId } = useContext(TabsContext);

  const [inputState, setInputState] = useState<patchUserInputStateType>(
    CONTROL_PATCH_USER_STATE
  );

  // set null id
  useEffect(() => {
    setTabId("");
  }, []);
  const { setErrorData } = useContext(alertContext);
  const { userData } = useContext(AuthContext);
  const { password, cnfPassword, gradient } = inputState;

  function handlePatchUser() {
    if (password !== cnfPassword) {
      setErrorData({
        title: "Error changing password",
        list: ["Passwords do not match"],
      });
      return;
    }

    updateUser(userData!.id, {password, profile_image: gradient});
  }

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }

  return (
    <>
      <Header />

      <div className="community-page-arrangement">
        <div className="community-page-nav-arrangement">
          <span className="community-page-nav-title">
            <IconComponent name="User" className="w-6" />
            Profile Settings
          </span>
        </div>
        <span className="community-page-description-text">
          Change your profile settings like your password and your profile
          picture.
        </span>
        <Form.Root
          onSubmit={(event) => {
            handlePatchUser();
            const data = Object.fromEntries(new FormData(event.currentTarget));
            event.preventDefault();
          }}
          className="flex justify-between px-6"
        >
          <div className="flex gap-4">
          <div className="mb-3 w-96">
            <Form.Field name="password">
              <Form.Label className="data-[invalid]:label-invalid">
                Password <span className="font-medium text-destructive">*</span>
              </Form.Label>

              <Form.Control asChild>
                <InputComponent
                  onChange={(value) => {
                    handleInput({ target: { name: "password", value } });
                  }}
                  value={password}
                  isForm
                  password={true}
                  required
                  placeholder="Password"
                  className="w-full"
                />
              </Form.Control>

              <Form.Message match="valueMissing" className="field-invalid">
                Please enter your password
              </Form.Message>
            </Form.Field>
          </div>
          <div className="mb-3 w-96">
            <Form.Field name="cnfPassword">
              <Form.Label className="data-[invalid]:label-invalid">
                Confirm Password{" "}
                <span className="font-medium text-destructive">*</span>
              </Form.Label>

              <InputComponent
                onChange={(value) => {
                  handleInput({ target: { name: "cnfPassword", value } });
                }}
                value={cnfPassword}
                isForm
                password={true}
                required
                placeholder="Confirm Password"
                className="w-full"
              />

              <Form.Message className="field-invalid" match="valueMissing">
                Please confirm your password
              </Form.Message>
            </Form.Field>
            <Form.Field name="gradient">
              <Form.Label className="data-[invalid]:label-invalid">
                Insert Gradient{" "}
                <span className="font-medium text-destructive">*</span>
              </Form.Label>

              <InputComponent
                onChange={(value) => {
                  handleInput({ target: { name: "gradient", value } });
                }}
                value={gradient}
                isForm
                password={true}
                required
                placeholder="Insert Gradient"
                className="w-full"
              />

              <Form.Message className="field-invalid" match="valueMissing">
                Please insert gradient
              </Form.Message>
            </Form.Field>
          </div>
          </div>
          <div className="w-40">
            <Form.Submit asChild>
              <Button className="mr-3 mt-6 w-full" type="submit">
                Save
              </Button>
            </Form.Submit>
          </div>
        </Form.Root>
      </div>
    </>
  );
}
