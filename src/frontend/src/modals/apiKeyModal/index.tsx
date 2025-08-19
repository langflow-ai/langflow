import IconComponent from "@/components/common/genericIconComponent";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { useEffect, useState } from "react";
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
      // If we're in the form stage, save the API key and show it
      if (apiKeyValue.trim()) {
        setShowKey(true);
        onSave?.(apiKeyValue);
      }
    }
  };

  const description = (
    <div className="pt-2">
      Add an <span className="text-primary">{provider} API key </span> to enable all {provider} models. For per-component overrides, use component controls → Override API Key. Manage {provider} and other providers in <span className="text-primary">Settings.</span>
    </div>
  )


  return (
    <BaseModal
      onSubmit={handleSubmitForm}
      size="smaller-h-full"
      open={open}
      setOpen={onClose}
    >
      <BaseModal.Header
        clampDescription={3}
        description={description}
      >
          
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
            <label className="text-sm font-medium text-foreground">
            {`${provider} API Key`} *
            </label>
            <InputComponent
              value={apiKeyValue}
              onChange={setApiKeyValue}
              placeholder={"Enter your API key"}
              password={true}
              editNode={false}
              required={true}
              autoFocus={true}
              hidePopover={true}
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
