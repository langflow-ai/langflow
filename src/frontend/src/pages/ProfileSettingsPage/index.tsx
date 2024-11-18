import {
  useResetPassword,
  useUpdateUser,
} from "@/controllers/API/queries/auth";
import * as Form from "@radix-ui/react-form";
import { cloneDeep } from "lodash";
import { useContext, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import Header from "../../components/headerComponent";
import InputComponent from "../../components/inputComponent";
import { Button } from "../../components/ui/button";
import {
  EDIT_PASSWORD_ALERT_LIST,
  EDIT_PASSWORD_ERROR_ALERT,
  SAVE_ERROR_ALERT,
  SAVE_SUCCESS_ALERT,
} from "../../constants/alerts_constants";
import { CONTROL_PATCH_USER_STATE } from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import useAlertStore from "../../stores/alertStore";
import {
  inputHandlerEventType,
  patchUserInputStateType,
} from "../../types/components";
import { gradients } from "../../utils/styleUtils";
import GradientChooserComponent from "../SettingsPage/pages/GeneralPage/components/ProfilePictureForm/components/profilePictureChooserComponent";
export default function ProfileSettingsPage(): JSX.Element {
  const [inputState, setInputState] = useState<patchUserInputStateType>(
    CONTROL_PATCH_USER_STATE,
  );
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { userData, setUserData } = useContext(AuthContext);
  const { password, cnfPassword, gradient } = inputState;

  const { mutate: mutateResetPassword } = useResetPassword();
  const { mutate: mutatePatchUser } = useUpdateUser();

  async function handlePatchUser() {
    if (password !== cnfPassword) {
      setErrorData({
        title: EDIT_PASSWORD_ERROR_ALERT,
        list: [EDIT_PASSWORD_ALERT_LIST],
      });
      return;
    }
    if (password !== "") {
      mutateResetPassword(
        { user_id: userData!.id, password: { password } },
        {
          onSuccess: successUpdates,
          onError: errorUpdates,
        },
      );
    }
    if (gradient !== "") {
      mutatePatchUser(
        { user_id: userData!.id, user: { profile_image: gradient } },
        {
          onSuccess: successUpdates,
          onError: errorUpdates,
        },
      );
    }
  }

  const errorUpdates = (error) => {
    setErrorData({
      title: SAVE_ERROR_ALERT,
      list: [(error as any).response.data.detail],
    });
  };

  const successUpdates = () => {
    if (gradient !== "") {
      let newUserData = cloneDeep(userData);
      newUserData!.profile_image = gradient;
      setUserData(newUserData);
    }
    handleInput({ target: { name: "password", value: "" } });
    handleInput({ target: { name: "cnfPassword", value: "" } });
    setSuccessData({ title: SAVE_SUCCESS_ALERT });
  };

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
          className="flex h-full flex-col px-6 pb-16"
        >
          <div className="flex h-full flex-col gap-4">
            <div className="flex gap-4">
              <div className="mb-3 w-96">
                <Form.Field name="password">
                  <Form.Label className="data-[invalid]:label-invalid">
                    Password{" "}
                  </Form.Label>
                  <InputComponent
                    id="pasword"
                    onChange={(value) => {
                      handleInput({ target: { name: "password", value } });
                    }}
                    value={password}
                    isForm
                    password={true}
                    placeholder="Password"
                    className="w-full"
                  />
                  <Form.Message match="valueMissing" className="field-invalid">
                    Please enter your password
                  </Form.Message>
                </Form.Field>
              </div>
              <div className="mb-3 w-96">
                <Form.Field name="cnfPassword">
                  <Form.Label className="data-[invalid]:label-invalid">
                    Confirm Password{" "}
                  </Form.Label>

                  <InputComponent
                    id="cnfPassword"
                    onChange={(value) => {
                      handleInput({ target: { name: "cnfPassword", value } });
                    }}
                    value={cnfPassword}
                    isForm
                    password={true}
                    placeholder="Confirm Password"
                    className="w-full"
                  />

                  <Form.Message className="field-invalid" match="valueMissing">
                    Please confirm your password
                  </Form.Message>
                </Form.Field>
              </div>
            </div>
            <Form.Field name="gradient">
              <Form.Label className="data-[invalid]:label-invalid">
                Profile Gradient{" "}
              </Form.Label>

              <div className="mt-4 w-[1010px]">
                <GradientChooserComponent
                  value={
                    gradient == ""
                      ? (userData?.profile_image ??
                        gradients[
                          parseInt(userData?.id ?? "", 30) % gradients.length
                        ])
                      : gradient
                  }
                  onChange={(value) => {
                    handleInput({ target: { name: "gradient", value } });
                  }}
                />
              </div>
            </Form.Field>
          </div>

          <div className="flex w-full justify-end">
            <div className="w-32">
              <Form.Submit asChild>
                <Button className="mr-3 mt-6 w-full" type="submit">
                  Save
                </Button>
              </Form.Submit>
            </div>
          </div>
        </Form.Root>
      </div>
    </>
  );
}
