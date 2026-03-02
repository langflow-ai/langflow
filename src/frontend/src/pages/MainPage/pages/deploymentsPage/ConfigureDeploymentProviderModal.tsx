import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  type DeploymentProvider,
  useDeleteDeploymentProvider,
  usePatchUpdateDeploymentProvider,
} from "@/controllers/API/queries/deployments/use-deployments";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";

type ConfigureDeploymentProviderModalProps = {
  open: boolean;
  provider: DeploymentProvider | null;
  onOpenChange: (open: boolean) => void;
};

export const ConfigureDeploymentProviderModal = ({
  open,
  provider,
  onOpenChange,
}: ConfigureDeploymentProviderModalProps) => {
  const queryClient = useQueryClient();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const [backendUrl, setBackendUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [accountId, setAccountId] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);

  const providerId = provider?.id || "";
  const providerKey = provider?.provider_key || "";
  const isWatsonxProvider = providerKey === "watsonx-orchestrate";

  const { mutate: updateProvider, isPending } =
    usePatchUpdateDeploymentProvider({ providerId });
  const { mutate: deleteProvider, isPending: isDeleting } =
    useDeleteDeploymentProvider({ providerId });

  useEffect(() => {
    if (!provider) {
      setBackendUrl("");
      setApiKey("");
      setAccountId("");
      return;
    }

    setBackendUrl(provider.backend_url || "");
    setApiKey("");
    setAccountId(provider.account_id || "");
    setDeleteOpen(false);
  }, [provider, open]);

  const hasChanges = useMemo(() => {
    if (!provider) {
      return false;
    }

    const backendChanged = backendUrl.trim() !== provider.backend_url;
    const accountChanged = isWatsonxProvider
      ? false
      : accountId.trim() !== (provider.account_id || "");
    const apiKeyChanged = apiKey.trim().length > 0;

    return backendChanged || accountChanged || apiKeyChanged;
  }, [provider, backendUrl, accountId, apiKey, isWatsonxProvider]);

  const handleSubmit = () => {
    if (!provider || !providerId) {
      setErrorData({ title: "No deployment provider selected." });
      return;
    }

    if (!backendUrl.trim()) {
      setErrorData({ title: "Backend URL is required." });
      return;
    }

    if (!hasChanges) {
      setErrorData({ title: "No changes to save." });
      return;
    }

    const nextAccountId = accountId.trim();
    const payload: {
      backend_url?: string;
      api_key?: string;
      account_id?: string | null;
    } = {};

    if (backendUrl.trim() !== provider.backend_url) {
      payload.backend_url = backendUrl.trim();
    }

    if (!isWatsonxProvider && nextAccountId !== (provider.account_id || "")) {
      payload.account_id = nextAccountId || null;
    }

    if (apiKey.trim()) {
      payload.api_key = apiKey.trim();
    }

    updateProvider(payload, {
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: ["useGetDeploymentProviders"],
        });
        setSuccessData({ title: "Deployment provider updated successfully" });
        onOpenChange(false);
      },
      onError: () => {
        setErrorData({
          title: "Could not update deployment provider",
          list: ["Check the provider values and try again."],
        });
      },
    });
  };

  const handleDelete = () => {
    if (!provider || !providerId) {
      setErrorData({ title: "No deployment provider selected." });
      return;
    }

    deleteProvider(undefined, {
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: ["useGetDeploymentProviders"],
        });
        setSuccessData({ title: "Deployment provider deleted successfully" });
        setDeleteOpen(false);
        onOpenChange(false);
      },
      onError: () => {
        setErrorData({
          title: "Could not delete deployment provider",
          list: ["Please remove related deployments first and try again."],
        });
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Configure Deployment Provider</DialogTitle>
          <DialogDescription>
            Update connection details for the selected deployment provider.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Provider</label>
            <Input value={providerKey} disabled />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">
              Backend URL <span className="text-destructive">*</span>
            </label>
            <Input
              value={backendUrl}
              onChange={(event) => setBackendUrl(event.target.value)}
              placeholder="https://api.<region>.watson-orchestrate.ibm.com/instances/<id>"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">API Key</label>
            <Input
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="Leave empty to keep existing API key"
              type="password"
            />
          </div>

          {!isWatsonxProvider && (
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">
                Account ID (optional)
              </label>
              <Input
                value={accountId}
                onChange={(event) => setAccountId(event.target.value)}
                placeholder="Provider account/tenant id"
              />
            </div>
          )}
        </div>

        <DialogFooter>
          <DeleteConfirmationModal
            open={deleteOpen}
            setOpen={setDeleteOpen}
            onConfirm={() => handleDelete()}
            description="deployment provider"
            note={providerKey ? `(${providerKey})` : ""}
          >
            <Button
              variant="destructive"
              onClick={() => setDeleteOpen(true)}
              disabled={isPending || isDeleting}
            >
              Delete Provider
            </Button>
          </DeleteConfirmationModal>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            loading={isPending}
            disabled={isDeleting}
          >
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
