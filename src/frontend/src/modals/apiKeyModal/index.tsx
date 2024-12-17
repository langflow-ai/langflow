import { useEffect, useState } from "react";
import IconComponent from "../../components/common/genericIconComponent";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { SAVE_API_KEY_ALERT } from "../../constants/constants";
import { usePostGlobalVariables } from "../../controllers/API/queries/variables";
import useAlertStore from "../../stores/alertStore";
import BaseModal from "../baseModal";

export default function APIKeyModal({
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
}) {
  const [apiKey, setApiKey] = useState("");
  const createVariable = usePostGlobalVariables();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  // Reset form when modal opens
  useEffect(() => {
    if (open) {
      setApiKey("");
    }
  }, [open]);

  const handleSave = async () => {
    try {
      await createVariable.mutateAsync({
        name: "OPENAI_API_KEY",
        value: apiKey,
        type: "secret",
        default_fields: ["voice_mode"],
      });
      setSuccessData({
        title: SAVE_API_KEY_ALERT,
      });
      setOpen(false);
    } catch (error) {
      console.error("Error saving API key:", error);
    }
  };

  return (
    <BaseModal size="small-h-full" open={open} setOpen={setOpen}>
      <BaseModal.Header>
        <span className="pr-2">Enter OpenAI API Key</span>
        <IconComponent
          name="Key"
          className="h-6 w-6 pl-1 text-primary"
          aria-hidden="true"
        />
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            Please enter your OpenAI API key to enable voice mode. Your key will
            be stored securely as the global variable OPENAI_API_KEY.
          </p>
          <Input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
            className="w-full"
            autoFocus
          />
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            className="px-8"
          >
            Cancel
          </Button>
          <Button disabled={!apiKey} onClick={handleSave} className="px-8">
            Save
          </Button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
