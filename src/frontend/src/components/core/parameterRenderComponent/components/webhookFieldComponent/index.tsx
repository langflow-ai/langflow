import { Button } from "@/components/ui/button";
import { AuthContext } from "@/contexts/authContext";
import { useGetBuildsMutation } from "@/controllers/API/queries/_builds/use-get-builds-pooling-mutation";
import SecretKeyModal from "@/modals/secretKeyModal";
import { getModalPropsApiKey } from "@/pages/SettingsPage/pages/ApiKeysPage/helpers/get-modal-props";
import { useContext, useEffect, useState } from "react";
import { ForwardedIconComponent } from "../../../../common/genericIconComponent";
import { InputProps, TextAreaComponentType } from "../../types";
import CopyFieldAreaComponent from "../copyFieldAreaComponent";
import TextAreaComponent from "../textAreaComponent";

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
  const { mutate: getBuildsMutation } = useGetBuildsMutation();

  const isBackendUrl = nodeInformationMetadata?.variableName === "endpoint";
  const isCurlWebhook = nodeInformationMetadata?.variableName === "curl";
  const showGenerateToken = isBackendUrl && !editNode;

  useEffect(() => {
    if (!editNode && isBackendUrl) {
      getBuildsMutation({
        flowId: nodeInformationMetadata?.flowId!,
      });
    }
  }, []);

  useEffect(() => {
    if (userData) {
      setUserId(userData.id);
    }
  }, [userData]);

  return (
    <div className="grid w-full gap-2">
      {isBackendUrl && (
        <div>
          <CopyFieldAreaComponent
            id={id}
            value={value}
            editNode={editNode}
            handleOnNewValue={handleOnNewValue}
            {...baseInputProps}
          />
        </div>
      )}

      {isCurlWebhook && (
        <div>
          <TextAreaComponent
            id={id}
            value={value}
            editNode={editNode}
            handleOnNewValue={handleOnNewValue}
            {...baseInputProps}
            nodeInformationMetadata={nodeInformationMetadata}
          />
        </div>
      )}

      {showGenerateToken && (
        <div>
          <SecretKeyModal
            modalProps={{ ...modalProps, size: "small-h-full" }}
            data={userId}
          >
            <Button
              size="sm"
              data-testid="generate_token_webhook_button"
              variant="outline"
              onClick={(e) => e.stopPropagation()}
            >
              <ForwardedIconComponent name="Key" className="h-4 w-4" />
              Generate token
            </Button>
          </SecretKeyModal>
        </div>
      )}
    </div>
  );
}
