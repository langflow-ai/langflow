import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import LangflowLogoColor from "@/assets/LangflowLogoColor.svg?react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
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
import { usePostCreateDeploymentProvider } from "@/controllers/API/queries/deployments/use-deployments";
import IBMSvg from "@/icons/IBM/ibm/IBM";
import useAlertStore from "@/stores/alertStore";

type RegisterDeploymentProviderModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

type ProviderOption = {
  key: string;
  label: string;
  iconType: "langflow" | "icon";
};

const PROVIDER_OPTIONS: ProviderOption[] = [
  {
    key: "watsonx-orchestrate",
    label: "watsonx Orchestrate",
    iconType: "icon",
  },
  {
    key: "langflow",
    label: "Langflow",
    iconType: "langflow",
  },
];

export const RegisterDeploymentProviderModal = ({
  open,
  onOpenChange,
}: RegisterDeploymentProviderModalProps) => {
  const queryClient = useQueryClient();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { mutate: createProvider, isPending } =
    usePostCreateDeploymentProvider();

  const [providerKey, setProviderKey] = useState("");
  const [backendUrl, setBackendUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [accountId, setAccountId] = useState("");

  const resetState = () => {
    setProviderKey("");
    setBackendUrl("");
    setApiKey("");
    setAccountId("");
  };

  const validate = (): string | null => {
    if (!providerKey.trim()) {
      return "Provider key is required.";
    }
    if (!backendUrl.trim()) {
      return "Backend URL is required.";
    }
    if (!apiKey.trim()) {
      return "API key is required.";
    }
    return null;
  };

  const handleSubmit = () => {
    const validationError = validate();
    if (validationError) {
      setErrorData({ title: validationError });
      return;
    }

    createProvider(
      {
        provider_key: providerKey.trim(),
        backend_url: backendUrl.trim(),
        api_key: apiKey.trim(),
        account_id:
          providerKey === "watsonx-orchestrate"
            ? undefined
            : accountId.trim() || undefined,
      },
      {
        onSuccess: async () => {
          await queryClient.invalidateQueries({
            queryKey: ["useGetDeploymentProviders"],
          });
          setSuccessData({
            title: "Deployment provider registered successfully",
          });
          onOpenChange(false);
          resetState();
        },
        onError: () => {
          setErrorData({
            title: "Could not register deployment provider",
            list: ["Check your backend URL/API key and try again."],
          });
        },
      },
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        onOpenChange(nextOpen);
        if (!nextOpen) {
          resetState();
        }
      }}
    >
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Register Deployment Provider</DialogTitle>
          <DialogDescription>
            Connect your deployment provider account to enable deployments.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">
              Provider <span className="text-destructive">*</span>
            </label>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {PROVIDER_OPTIONS.map((provider) => (
                <button
                  key={provider.key}
                  type="button"
                  onClick={() => setProviderKey(provider.key)}
                  className={`flex items-center gap-3 rounded-lg border bg-background p-3 text-left transition-colors ${
                    providerKey === provider.key
                      ? "border-primary"
                      : "border-border hover:border-muted-foreground"
                  }`}
                >
                  <div
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border ${
                      provider.key === "watsonx-orchestrate"
                        ? "bg-white"
                        : "bg-card"
                    }`}
                  >
                    {provider.key === "watsonx-orchestrate" ? (
                      <IBMSvg className="h-3.5 w-3.5 text-[#0F62FE]" />
                    ) : provider.iconType === "langflow" ? (
                      <LangflowLogoColor className="h-4 w-4" />
                    ) : (
                      <ForwardedIconComponent
                        name="Cloud"
                        className="h-4 w-4 text-foreground"
                      />
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{provider.label}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {providerKey && (
            <>
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
                <label className="text-sm font-medium">
                  API Key <span className="text-destructive">*</span>
                </label>
                <Input
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="Paste provider API key"
                  type="password"
                />
              </div>

              {providerKey !== "watsonx-orchestrate" && (
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
            </>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => {
              onOpenChange(false);
              resetState();
            }}
          >
            Cancel
          </Button>
          <Button onClick={handleSubmit} loading={isPending}>
            Register Provider
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
