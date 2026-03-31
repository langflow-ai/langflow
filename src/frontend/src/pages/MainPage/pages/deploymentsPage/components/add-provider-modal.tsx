import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { usePostProviderAccount } from "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account";
import useAlertStore from "@/stores/alertStore";
import type { ProviderCredentials } from "../types";

interface AddProviderModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
}

const EMPTY_CREDENTIALS: ProviderCredentials = {
  name: "",
  provider_key: "watsonx",
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
  const setErrorData = useAlertStore((state) => state.setErrorData);

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
      const message =
        err instanceof Error ? err.message : "Something went wrong";
      setErrorData({
        title: "Failed to create environment",
        list: [message],
      });
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

          <div className="flex flex-col">
            <span className="pb-2 text-sm font-medium">
              Name <span className="text-destructive">*</span>
            </span>
            <Input
              type="text"
              placeholder="e.g. Production"
              className="bg-muted"
              value={credentials.name}
              onChange={(e) =>
                setCredentials({ ...credentials, name: e.target.value })
              }
            />
          </div>

          <div className="flex flex-col">
            <span className="pb-2 text-sm font-medium">
              API Key <span className="text-destructive">*</span>
            </span>
            <Input
              type="password"
              placeholder="Enter your API key"
              className="bg-muted"
              value={credentials.api_key}
              onChange={(e) =>
                setCredentials({ ...credentials, api_key: e.target.value })
              }
            />
          </div>

          <div className="flex flex-col">
            <span className="pb-2 text-sm font-medium">
              Service Environment URL{" "}
              <span className="text-destructive">*</span>
            </span>
            <Input
              type="url"
              placeholder="https://api.example.com"
              className="bg-muted"
              value={credentials.provider_url}
              onChange={(e) =>
                setCredentials({
                  ...credentials,
                  provider_url: e.target.value,
                })
              }
            />
          </div>
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
