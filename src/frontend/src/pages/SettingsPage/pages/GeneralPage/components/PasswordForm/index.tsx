import * as Form from "@radix-ui/react-form";
import { useTranslation } from "react-i18next";
import type { inputHandlerEventType } from "@/types/components";
import InputComponent from "../../../../../../components/core/parameterRenderComponent/components/inputComponent";
import { Button } from "../../../../../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../../../../../../components/ui/card";

type PasswordFormComponentProps = {
  currentPassword: string;
  password: string;
  cnfPassword: string;
  handleInput: (event: inputHandlerEventType) => void;
  handlePatchPassword: () => void;
};
const PasswordFormComponent = ({
  currentPassword,
  password,
  cnfPassword,
  handleInput,
  handlePatchPassword,
}: PasswordFormComponentProps) => {
  const { t } = useTranslation();
  return (
    <>
      <Form.Root
        aria-label={t("settings.passwordTitle")}
        onSubmit={(event) => {
          handlePatchPassword();
          event.preventDefault();
        }}
      >
        <Card x-chunk="dashboard-04-chunk-2">
          <CardHeader>
            <CardTitle>{t("settings.passwordTitle")}</CardTitle>
            <CardDescription>
              {t("settings.passwordDescription")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex w-full flex-col gap-4 md:flex-row">
              <Form.Field name="currentPassword" className="w-full">
                <InputComponent
                  id="currentPassword"
                  onChange={(value) => {
                    handleInput({
                      target: { name: "currentPassword", value },
                    });
                  }}
                  value={currentPassword}
                  isForm
                  password={true}
                  required
                  placeholder={t("settings.currentPasswordPlaceholder")}
                  className="w-full"
                />
                <Form.Message match="valueMissing" className="field-invalid">
                  {t("settings.currentPasswordRequired")}
                </Form.Message>
              </Form.Field>
              <Form.Field name="password" className="w-full">
                <InputComponent
                  id="pasword"
                  onChange={(value) => {
                    handleInput({ target: { name: "password", value } });
                  }}
                  value={password}
                  isForm
                  password={true}
                  required
                  placeholder={t("settings.passwordPlaceholder")}
                  className="w-full"
                />
                <Form.Message match="valueMissing" className="field-invalid">
                  {t("settings.passwordRequired")}
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
                  required
                  placeholder={t("settings.confirmPasswordPlaceholder")}
                  className="w-full"
                />

                <Form.Message className="field-invalid" match="valueMissing">
                  {t("settings.confirmPasswordRequired")}
                </Form.Message>
              </Form.Field>
            </div>
          </CardContent>
          <CardFooter className="border-t px-6 py-4">
            <Form.Submit asChild>
              <Button type="submit">{t("settings.saveButton")}</Button>
            </Form.Submit>
          </CardFooter>
        </Card>
      </Form.Root>
    </>
  );
};
export default PasswordFormComponent;
