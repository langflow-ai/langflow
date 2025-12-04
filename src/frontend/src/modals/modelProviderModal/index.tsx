import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog";
import {
  PROVIDER_VARIABLE_MAPPING,
  VARIABLE_CATEGORY,
} from "@/constants/providerConstants";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useUpdateEnabledModels } from "@/controllers/API/queries/models/use-update-enabled-models";
import { usePostGlobalVariables } from "@/controllers/API/queries/variables";
import ProviderList from "@/modals/modelProviderModal/components/ProviderList";
import { Model, Provider } from "@/modals/modelProviderModal/components/types";
import useAlertStore from "@/stores/alertStore";

import { cn } from "@/utils/utils";
import ModelProviderEdit from "./components/ModelProviderEdit";
import ModelSelection from "./components/ModelSelection";

interface ModelProviderModalProps {
  open: boolean;
  onClose: () => void;
  modeltype: "llm" | "embeddings";
}

const ModelProviderModal = ({
  open,
  onClose,
  modeltype,
}: ModelProviderModalProps) => {
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null,
  );

  const [isEditing, setIsEditing] = useState(true);
  const [authName, setAuthName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiBase, setApiBase] = useState("");

  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutate: createGlobalVariable, isPending } = usePostGlobalVariables();
  const { mutate: updateEnabledModels } = useUpdateEnabledModels();

  // Reset form and pending changes when provider changes
  useEffect(() => {
    setAuthName("");
    setApiKey("");
    setApiBase("");
  }, [selectedProvider?.provider]);

  // Update enabled models when toggled
  const handleModelToggle = (modelName: string, enabled: boolean) => {
    if (!selectedProvider?.provider) return;

    updateEnabledModels(
      {
        updates: [
          {
            provider: selectedProvider.provider,
            model_id: modelName,
            enabled,
          },
        ],
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] });
        },
      },
    );
  };

  const handleProviderSelect = (provider: Provider) => {
    setSelectedProvider((prev) =>
      prev?.provider === provider.provider ? null : provider,
    );
    setIsEditing(!provider.is_enabled);
  };

  const handleConfigureProvider = () => {
    if (!selectedProvider || !apiKey.trim()) return;

    const variableName = PROVIDER_VARIABLE_MAPPING[selectedProvider.provider];

    if (!variableName) {
      setErrorData({
        title: "Invalid Provider",
        list: [`Provider "${selectedProvider.provider}" is not supported.`],
      });
      return;
    }

    createGlobalVariable(
      {
        name: variableName,
        value: apiKey,
        type: VARIABLE_CATEGORY.CREDENTIAL,
        category: VARIABLE_CATEGORY.GLOBAL,
        default_fields: [],
      },
      {
        onSuccess: () => {
          setSuccessData({
            title: `${selectedProvider.provider} API Key Saved`,
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

          // Reset form and switch to model selection view
          setApiKey("");
          setAuthName("");
          setApiBase("");
          // Update local state to reflect enabled status
          setSelectedProvider((prev) =>
            prev ? { ...prev, is_enabled: true } : null,
          );
          setIsEditing(false);
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
  };

  // Handle modal close - refresh if updates were made
  const handleClose = () => {
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <DialogContent className="flex flex-col overflow-hidden rounded-xl p-0 max-w-[950px] gap-0">
        {/* model provider header */}
        <DialogHeader className="flex w-full border-b px-4 py-3">
          <div className="flex justify-start items-center gap-3">
            <ForwardedIconComponent name="Brain" className="w-5 h-5" />
            <div className="text-[13px] font-semibold ">Model providers</div>
          </div>
        </DialogHeader>

        {/* model provider list */}
        <div className="flex flex-row w-full overflow-hidden">
          <div
            className={cn(
              "flex border-r p-2 flex-col transition-all duration-300 ease-in-out",
              selectedProvider ? "w-1/2" : "w-full",
            )}
          >
            <ProviderList
              modelType={modeltype}
              onProviderSelect={handleProviderSelect}
              selectedProviderName={selectedProvider?.provider ?? null}
            />
          </div>

          {/* Model Provider sub header */}
          <div
            className={cn(
              "flex flex-col gap-1 transition-all duration-300 ease-in-out overflow-hidden",
              selectedProvider
                ? "w-1/2 opacity-100 translate-x-0"
                : "w-0 opacity-0 translate-x-full",
            )}
          >
            <div className="flex flex-row items-center gap-1 border-b p-4 min-w-[300px]">
              <ForwardedIconComponent
                name={selectedProvider?.icon || "Bot"}
                className={cn(
                  "w-5 h-5 flex-shrink-0 transition-all",
                  !selectedProvider?.is_enabled && "grayscale opacity-50",
                )}
              />
              <span className="text-[13px] font-semibold pl-2 mr-auto">
                {selectedProvider?.provider || "Unknown Provider"}
              </span>
              {selectedProvider?.is_enabled && (
                <Button
                  variant="menu"
                  size="icon"
                  unstyled
                  onClick={() => setIsEditing(!isEditing)}
                  className=""
                >
                  <ForwardedIconComponent
                    name={"Pencil"}
                    className={cn(
                      "h-4 w-4 flex-shrink-0 ",
                      !isEditing
                        ? "text-primary hover:text-muted-foreground"
                        : "text-muted-foreground hover:text-primary",
                    )}
                  />
                </Button>
              )}
            </div>

            {/* model provider selection */}
            <div className="relative overflow-x-hidden min-w-[300px] ">
              <div
                className={cn(
                  "flex flex-col p-4 gap-3 transition-all duration-300 ease-in-out min-h-[480px] h-[480px]",
                  isEditing
                    ? "opacity-0 -translate-x-full absolute inset-0"
                    : "opacity-100 translate-x-0",
                )}
              >
                <ModelSelection
                  modelType={modeltype}
                  availableModels={selectedProvider?.models || []}
                  onModelToggle={handleModelToggle}
                  providerName={selectedProvider?.provider}
                />
              </div>

              {/* Edit */}
              <div
                className={cn(
                  "flex flex-col transition-all duration-300 ease-in-out h-[403px]",
                  isEditing
                    ? "opacity-100 translate-x-0"
                    : "opacity-0 translate-x-full absolute inset-0",
                )}
              >
                <ModelProviderEdit
                  authName={authName}
                  onAuthNameChange={setAuthName}
                  apiKey={apiKey}
                  onApiKeyChange={setApiKey}
                  apiBase={apiBase}
                  onApiBaseChange={setApiBase}
                  providerName={selectedProvider?.provider}
                />
                {/* <ModelProviderActive
                  activeLLMs={activeLLMNames}
                  activeEmbeddings={activeEmbeddingNames}
                /> */}
              </div>
            </div>

            {/* model provider footer */}
            {isEditing && (
              <div className="flex justify-end border-t p-4 min-w-[300px] gap-2">
                <Button className="w-full" onClick={handleConfigureProvider}>
                  Configure
                </Button>
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ModelProviderModal;
