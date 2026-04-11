import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
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
  url: "",
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
    credentials.url.trim() !== "";

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
        provider_data: {
          url: credentials.url.trim(),
          api_key: credentials.api_key.trim(),
        },
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
        <DialogTitle data-testid="add-provider-modal-title">
          Add Environment
        </DialogTitle>
        <DialogDescription className="sr-only">
          Add a new watsonx Orchestrate environment.
        </DialogDescription>

        <div className="flex flex-col gap-4 pt-2">
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3 rounded-lg border border-border bg-muted p-3">
              <ForwardedIconComponent
                name="WatsonxOrchestrate"
                className="h-8 w-8 text-foreground"
              />
              <span className="text-sm font-medium">watsonx Orchestrate</span>
              <Badge variant="purpleStatic" size="xq" className="shrink-0">
                Beta
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              Configure your watsonx Orchestrate credentials below. Sign in or
              sign up to{" "}
              <a
                href="https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=api-getting-started"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-primary hover:underline"
              >
                find your credentials
              </a>
              .
            </p>
          </div>

          <ProviderCredentialsForm
            credentials={credentials}
            onCredentialsChange={setCredentials}
          />
        </div>

        <div className="flex items-center justify-end gap-3 pt-4">
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isSaving}
            data-testid="add-provider-cancel"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={!canSave || isSaving}
            data-testid="add-provider-save"
          >
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
