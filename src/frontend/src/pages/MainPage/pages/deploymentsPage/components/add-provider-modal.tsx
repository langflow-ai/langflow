import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { usePatchProviderAccount } from "@/controllers/API/queries/deployment-provider-accounts/use-patch-provider-account";
import { usePostProviderAccount } from "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account";
import { decorateWxoUrl } from "@/utils/decorate-wxo-url";
import { useErrorAlert } from "../hooks/use-error-alert";
import type { ProviderAccount, ProviderCredentials } from "../types";
import ProviderCredentialsForm from "./provider-credentials-form";

interface AddProviderModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  provider?: ProviderAccount | null;
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
  provider = null,
}: AddProviderModalProps) {
  const isEditMode = !!provider;
  const [credentials, setCredentials] =
    useState<ProviderCredentials>(EMPTY_CREDENTIALS);
  const [isSaving, setIsSaving] = useState(false);

  const { mutateAsync: createProviderAccount } = usePostProviderAccount();
  const { mutateAsync: updateProviderAccount } = usePatchProviderAccount();
  const showError = useErrorAlert();

  const trimmedName = credentials.name.trim();
  const trimmedApiKey = credentials.api_key.trim();
  const trimmedUrl = credentials.url.trim();
  const providerUrl =
    typeof provider?.provider_data?.url === "string"
      ? provider.provider_data.url
      : "";
  const initialName = provider?.name ?? "";
  const canSave = isEditMode
    ? trimmedName !== "" &&
      (trimmedName !== initialName || trimmedApiKey !== "")
    : trimmedName !== "" && trimmedApiKey !== "" && trimmedUrl !== "";

  useEffect(() => {
    if (!open) return;
    setCredentials(
      provider
        ? {
            name: provider.name,
            provider_key: provider.provider_key,
            url: providerUrl,
            api_key: "",
          }
        : EMPTY_CREDENTIALS,
    );
  }, [open, provider, providerUrl]);

  function handleClose() {
    if (isSaving) return;
    setCredentials(EMPTY_CREDENTIALS);
    setOpen(false);
  }

  async function handleSave() {
    if (!canSave) return;
    try {
      setIsSaving(true);
      if (provider) {
        await updateProviderAccount({
          provider_id: provider.id,
          name: trimmedName,
          ...(trimmedApiKey
            ? {
                provider_data: {
                  api_key: trimmedApiKey,
                },
              }
            : {}),
        });
      } else {
        await createProviderAccount({
          name: trimmedName,
          provider_key: credentials.provider_key,
          provider_data: {
            url: trimmedUrl,
            api_key: trimmedApiKey,
          },
        });
      }
      setCredentials(EMPTY_CREDENTIALS);
      setOpen(false);
    } catch (err: unknown) {
      showError(
        provider
          ? "Failed to update environment"
          : "Failed to create environment",
        err,
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(value) => !value && handleClose()}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogTitle data-testid="add-provider-modal-title">
          {provider ? "Configure Environment" : "Add Environment"}
        </DialogTitle>
        <DialogDescription className="sr-only">
          {provider
            ? `Configure environment ${provider.name}.`
            : "Add a new watsonx Orchestrate environment."}
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
              {provider ? (
                "Update environment name or rotate API key. Service instance URL is fixed after creation."
              ) : (
                <>
                  Configure your watsonx Orchestrate credentials below. New to
                  wxO?{" "}
                  <a
                    href={decorateWxoUrl(
                      "https://www.ibm.com/products/watsonx-orchestrate#pricing",
                      "signup-pricing",
                    )}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary hover:underline"
                  >
                    Sign up for watsonx Orchestrate
                  </a>
                  . Already have an account?{" "}
                  <a
                    href={decorateWxoUrl(
                      "https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=api-getting-started",
                      "docs-credentials",
                    )}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary hover:underline"
                  >
                    Find your credentials
                  </a>
                  .
                </>
              )}
            </p>
          </div>

          <ProviderCredentialsForm
            credentials={credentials}
            onCredentialsChange={setCredentials}
            apiKeyRequired={!provider}
            apiKeyPlaceholder={
              provider ? "Enter a new API key" : "Enter your API key"
            }
            urlRequired={!provider}
            urlReadOnly={!!provider}
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
            {isSaving ? "Saving..." : provider ? "Update" : "Save"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
