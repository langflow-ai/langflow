import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { usePostProviderAccount } from "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account";
import { useErrorAlert } from "../hooks/use-error-alert";
import type { ProviderCredentials } from "../types";
import ProviderCredentialsForm from "./provider-credentials-form";

interface AddProviderModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
}

const EMPTY_CREDENTIALS: ProviderCredentials = {
  name: "",
  provider_key: "watsonx-orchestrate",
  provider_url: "",
  api_key: "",
};

export default function AddProviderModal({
  open,
  setOpen,
}: AddProviderModalProps) {
  const [credentials, setCredentials] =
    useState<ProviderCredentials>(EMPTY_CREDENTIALS);
  const [isSaving, setIsSaving] = useState(false);

  const { mutateAsync: createProviderAccount } = usePostProviderAccount();
  const showError = useErrorAlert();

  const canSave =
    credentials.name.trim() !== "" &&
    credentials.api_key.trim() !== "" &&
    credentials.provider_url.trim() !== "";

  function handleClose() {
    if (isSaving) return;
    setCredentials(EMPTY_CREDENTIALS);
    setOpen(false);
  }

  async function handleSave() {
    if (!canSave) return;
    try {
      setIsSaving(true);
      await createProviderAccount({
        name: credentials.name.trim(),
        provider_key: credentials.provider_key,
        provider_url: credentials.provider_url.trim(),
        provider_data: { api_key: credentials.api_key.trim() },
      });
      setCredentials(EMPTY_CREDENTIALS);
      setOpen(false);
    } catch (err: unknown) {
      showError("Failed to create environment", err);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(value) => !value && handleClose()}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogTitle>Add Environment</DialogTitle>
        <DialogDescription>
          Configure your watsonx Orchestrate credentials below.
        </DialogDescription>

        <div className="flex flex-col gap-4 pt-2">
          <div className="flex items-center gap-3 rounded-lg border border-border bg-muted p-3">
            <ForwardedIconComponent
              name="Bot"
              className="h-8 w-8 text-foreground"
            />
            <span className="text-sm font-medium">watsonx Orchestrate</span>
          </div>

          <ProviderCredentialsForm
            credentials={credentials}
            onCredentialsChange={setCredentials}
          />
        </div>

        <div className="flex items-center justify-end gap-3 pt-4">
          <Button variant="outline" onClick={handleClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!canSave || isSaving}>
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
