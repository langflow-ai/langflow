import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { Input } from "@/components/ui/input";
import {
  PROVIDER_VARIABLE_MAPPING,
  VARIABLE_CATEGORY,
} from "@/constants/providerConstants";
import { usePostGlobalVariables } from "@/controllers/API/queries/variables";
import { COPIED_NOTICE_ALERT } from "../../constants/alerts_constants";
import useAlertStore from "../../stores/alertStore";
import BaseModal from "../baseModal";

interface ApiKeyModalProps {
  open: boolean;
  onClose: () => void;
  provider?: string;
  onSave?: (apiKey: string) => void;
}

export default function ApiKeyModal({
  open,
  onClose,
  provider = "Provider",
  onSave,
}: ApiKeyModalProps) {
  const [apiKeyName, setApiKeyName] = useState("");
  const [apiKeyValue, setApiKeyValue] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [textCopied, setTextCopied] = useState(true);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const queryClient = useQueryClient();
  const { mutate: createGlobalVariable, isPending } = usePostGlobalVariables();

  useEffect(() => {
    if (open) {
      resetForm();
      setShowKey(false);
    }
  }, [open]);

  const resetForm = () => {
    setApiKeyName("");
    setApiKeyValue("");
  };

  const handleSubmitForm = () => {
    if (showKey) {
      // If we're showing the key, close the modal
      onClose();
    } else {
      // If we're in the form stage, save the API key
      if (apiKeyValue.trim()) {
        const variableName = PROVIDER_VARIABLE_MAPPING[provider];

        if (!variableName) {
          setErrorData({
            title: "Invalid Provider",
            list: [`Provider "${provider}" is not supported.`],
          });
          return;
        }

        // TODO: Add validation for API key format if needed
        createGlobalVariable(
          {
            name: variableName,
            value: apiKeyValue,
            type: VARIABLE_CATEGORY.CREDENTIAL,
            category: VARIABLE_CATEGORY.GLOBAL,
            default_fields: [],
          },
          {
            onSuccess: () => {
              setSuccessData({
                title: `${provider} API Key Saved`,
              });
              // Invalidate caches to refresh the UI
              queryClient.invalidateQueries({
                queryKey: ["useGetModelProviders"],
              });
              queryClient.invalidateQueries({
                queryKey: ["useGetEnabledModels"],
              });
              queryClient.invalidateQueries({
                queryKey: ["useGetGlobalVariables"],
              });
              queryClient.invalidateQueries({
                queryKey: ["useGetDefaultModel"],
              });
              // Force refresh flow data to update node templates with new model options
              queryClient.refetchQueries({
                queryKey: ["flows"],
              });
              onSave?.(apiKeyValue);
              onClose();
            },
            onError: (error: any) => {
              setErrorData({
                title: "Error Saving API Key",
                list: [
                  error?.response?.data?.detail ||
                    "An unexpected error occurred while saving the API key. Please try again.",
                ],
              });
            },
          },
        );
      }
    }
  };

  const description = (
    <div className="pt-2 text-primary">
      Add an <span className="text-muted-foreground">{provider} API key </span>{" "}
      to enable all {provider} models. For per-component overrides, use
      component controls → Override API Key. Manage {provider} and other
      providers in <span className="text-muted-foreground">Settings.</span>
    </div>
  );

  return (
    <BaseModal
      onSubmit={handleSubmitForm}
      size="smaller-h-full"
      open={open}
      setOpen={onClose}
    >
      <BaseModal.Header clampDescription={3} description={description}>
        <IconComponent
          name="Key"
          className="h-6 w-6 mr-2 text-foreground"
          aria-hidden="true"
        />

        <span className="pr-2">Enable {provider} Model</span>
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium">
              {`${provider} API Key`} *
            </label>
            <Input
              value={apiKeyValue}
              onChange={(e) => setApiKeyValue(e.target.value)}
              placeholder={"Enter your API key"}
              type="password"
              required
              autoFocus
            />
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Save Key",
        }}
      />
    </BaseModal>
  );
}
