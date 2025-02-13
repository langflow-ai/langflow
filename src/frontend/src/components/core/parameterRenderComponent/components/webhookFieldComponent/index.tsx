import { Button } from "@/components/ui/button";
import { AuthContext } from "@/contexts/authContext";
import { useGetBuildsMutation } from "@/controllers/API/queries/_builds/use-get-builds-mutation";
import SecretKeyModal from "@/modals/secretKeyModal";
import { getModalPropsApiKey } from "@/pages/SettingsPage/pages/ApiKeysPage/helpers/get-modal-props";
import { useContext, useEffect, useState } from "react";
import { ForwardedIconComponent } from "../../../../common/genericIconComponent";
import { InputProps, TextAreaComponentType } from "../../types";
import CopyFieldAreaComponent from "../copyFieldAreaComponent";

export default function WebhookFieldComponent({
  value,
  handleOnNewValue,
  editNode = false,
  id = "",
  nodeInformationMetadata,
  ...baseInputProps
}: InputProps<string, TextAreaComponentType>): JSX.Element {
  const { userData } = useContext(AuthContext);
  const [userId, setUserId] = useState("");
  const modalProps = getModalPropsApiKey();
  useEffect(() => {
    if (userData) {
      setUserId(userData.id);
    }
  }, [userData]);

  const { mutate: getBuildsMutation } = useGetBuildsMutation();

  useEffect(() => {
    getBuildsMutation({
      flowId: nodeInformationMetadata?.flowId!,
      pollingInterval: 5,
    });
  }, []);

  return (
    <div className="grid w-full gap-2">
      <div>
        <CopyFieldAreaComponent
          id={id}
          value={value}
          editNode={editNode}
          handleOnNewValue={handleOnNewValue}
          {...baseInputProps}
        />
      </div>
      <div>
        <SecretKeyModal
          modalProps={{ ...modalProps, size: "small-h-full" }}
          data={userId}
        >
          <Button
            size="sm"
            data-testid="generate_token_webhook_button"
            variant="outline"
          >
            <ForwardedIconComponent name="Key" className="h-4 w-4" />
            Generate token
          </Button>
        </SecretKeyModal>
      </div>
    </div>
  );
}
