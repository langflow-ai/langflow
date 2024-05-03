import * as Form from "@radix-ui/react-form";
import { cloneDeep } from "lodash";
import { useContext, useEffect, useState } from "react";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import GradientChooserComponent from "../../../../components/gradientChooserComponent";
import InputComponent from "../../../../components/inputComponent";
import { Button } from "../../../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../../../../components/ui/card";
import {
  EDIT_PASSWORD_ALERT_LIST,
  EDIT_PASSWORD_ERROR_ALERT,
  SAVE_ERROR_ALERT,
  SAVE_SUCCESS_ALERT,
} from "../../../../constants/alerts_constants";
import { CONTROL_PATCH_USER_STATE } from "../../../../constants/constants";
import { AuthContext } from "../../../../contexts/authContext";
import { resetPassword, updateUser } from "../../../../controllers/API";
import useAlertStore from "../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import {
  inputHandlerEventType,
  patchUserInputStateType,
} from "../../../../types/components";
import { gradients } from "../../../../utils/styleUtils";

export default function GeneralPage() {
  const setCurrentFlowId = useFlowsManagerStore(
    (state) => state.setCurrentFlowId
  );

  const [inputState, setInputState] = useState<patchUserInputStateType>(
    CONTROL_PATCH_USER_STATE
  );

  const { autoLogin } = useContext(AuthContext);

  // set null id
  useEffect(() => {
    setCurrentFlowId("");
  }, []);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { userData, setUserData } = useContext(AuthContext);
  const { password, cnfPassword, gradient } = inputState;

  async function handlePatchPassword() {
    if (password !== cnfPassword) {
      setErrorData({
        title: EDIT_PASSWORD_ERROR_ALERT,
        list: [EDIT_PASSWORD_ALERT_LIST],
      });
      return;
    }
    try {
      if (password !== "") await resetPassword(userData!.id, { password });
      handleInput({ target: { name: "password", value: "" } });
      handleInput({ target: { name: "cnfPassword", value: "" } });
      setSuccessData({ title: SAVE_SUCCESS_ALERT });
    } catch (error) {
      setErrorData({
        title: SAVE_ERROR_ALERT,
        list: [(error as any).response.data.detail],
      });
    }
  }

  async function handlePatchGradient() {
    try {
      if (gradient !== "")
        await updateUser(userData!.id, { profile_image: gradient });
      if (gradient !== "") {
        let newUserData = cloneDeep(userData);
        newUserData!.profile_image = gradient;

        setUserData(newUserData);
      }
      setSuccessData({ title: SAVE_SUCCESS_ALERT });
    } catch (error) {
      setErrorData({
        title: SAVE_ERROR_ALERT,
        list: [(error as any).response.data.detail],
      });
    }
  }

  function handleInput({
    target: { name, value },
  }: inputHandlerEventType): void {
    setInputState((prev) => ({ ...prev, [name]: value }));
  }
  return (
    <div className="flex h-full w-full flex-col gap-6">
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            General
            <ForwardedIconComponent
              name="SlidersHorizontal"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            Manage settings related to Langflow and your account.
          </p>
        </div>
      </div>

      <div className="grid gap-6">
        
            <Form.Root
              onSubmit={(event) => {
                handlePatchGradient();
                event.preventDefault();
              }}
            >
              <Card x-chunk="dashboard-04-chunk-1">
                <CardHeader>
                  <CardTitle>Profile Gradient</CardTitle>
                  <CardDescription>
                    Choose the gradient that appears as your profile picture.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="py-2">
                    <GradientChooserComponent
                      value={
                        gradient == ""
                          ? userData?.profile_image ??
                            gradients[
                              parseInt(userData?.id ?? "", 30) %
                                gradients.length
                            ]
                          : gradient
                      }
                      onChange={(value) => {
                        handleInput({ target: { name: "gradient", value } });
                      }}
                    />
                  </div>
                </CardContent>
                <CardFooter className="border-t px-6 py-4">
                  <Form.Submit asChild>
                    <Button type="submit">Save</Button>
                  </Form.Submit>
                </CardFooter>
              </Card>
            </Form.Root>{!autoLogin && (
            <Form.Root
              onSubmit={(event) => {
                handlePatchPassword();
                event.preventDefault();
              }}
            >
              <Card x-chunk="dashboard-04-chunk-2">
                <CardHeader>
                  <CardTitle>Password</CardTitle>
                  <CardDescription>
                    Type your new password and confirm it.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex w-full gap-4">
                    <Form.Field name="password" className="w-full">
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
                      <Form.Message
                        match="valueMissing"
                        className="field-invalid"
                      >
                        Please enter your password
                      </Form.Message>
                    </Form.Field>
                    <Form.Field name="cnfPassword" className="w-full">
                      <InputComponent
                        id="cnfPassword"
                        onChange={(value) => {
                          handleInput({
                            target: { name: "cnfPassword", value },
                          });
                        }}
                        value={cnfPassword}
                        isForm
                        password={true}
                        placeholder="Confirm Password"
                        className="w-full"
                      />

                      <Form.Message
                        className="field-invalid"
                        match="valueMissing"
                      >
                        Please confirm your password
                      </Form.Message>
                    </Form.Field>
                  </div>
                </CardContent>
                <CardFooter className="border-t px-6 py-4">
                  <Form.Submit asChild>
                    <Button type="submit">Save</Button>
                  </Form.Submit>
                </CardFooter>
              </Card>
            </Form.Root>
        )}
      </div>
    </div>
  );
}
