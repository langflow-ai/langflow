import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  NO_API_KEY_PROVIDERS,
  PROVIDER_VARIABLE_MAPPING,
  VARIABLE_CATEGORY,
} from "@/constants/providerConstants";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useUpdateEnabledModels } from "@/controllers/API/queries/models/use-update-enabled-models";
import {
  useGetGlobalVariables,
  usePatchGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import { useDebounce } from "@/hooks/use-debounce";
import ProviderList from "@/modals/modelProviderModal/components/ProviderList";
import { Model, Provider } from "@/modals/modelProviderModal/components/types";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import ModelProviderEdit from "./components/ModelProviderEdit";
import ModelSelection from "./components/ModelSelection";

interface ModelProviderModalProps {
  open: boolean;
  onClose: () => void;
  modeltype: "llm" | "embeddings" | "all";
}

const ModelProviderModal = ({
  open,
  onClose,
  modeltype,
}: ModelProviderModalProps) => {
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null,
  );

  const [isEditing, setIsEditing] = useState(false);
  const [authName, setAuthName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [validationFailed, setValidationFailed] = useState(false);

  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutate: createGlobalVariable, isPending: isCreating } =
    usePostGlobalVariables();
  const { mutate: updateGlobalVariable, isPending: isUpdating } =
    usePatchGlobalVariables();
  const { data: globalVariables = [] } = useGetGlobalVariables();

  const isPending = isCreating || isUpdating;
  const { mutate: updateEnabledModels } = useUpdateEnabledModels();

  // Track if change came from user input
  const isUserInputRef = useRef(false);

  // Reset form and pending changes when provider changes
  useEffect(() => {
    setAuthName("");
    setApiKey("");
    setApiBase("");
    setValidationFailed(false);
  }, [selectedProvider?.provider]);

  // Debounced auto-configure when API key changes from user input
  const debouncedConfigureProvider = useDebounce(() => {
    if (apiKey.trim() && selectedProvider && isUserInputRef.current) {
      handleConfigureProvider();
      isUserInputRef.current = false;
    }
  }, 800);

  useEffect(() => {
    if (apiKey.trim() && isUserInputRef.current) {
      debouncedConfigureProvider();
    }
  }, [apiKey, debouncedConfigureProvider]);

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

  const requiresApiKey = useMemo(() => {
    if (!selectedProvider) return true;
    return !NO_API_KEY_PROVIDERS.includes(selectedProvider.provider);
  }, [selectedProvider]);

  const handleActivateNoApiKeyProvider = () => {
    if (!selectedProvider) return;

    const variableName = PROVIDER_VARIABLE_MAPPING[selectedProvider.provider];

    if (!variableName) {
      setErrorData({
        title: "Invalid Provider",
        list: [`Provider "${selectedProvider.provider}" is not supported.`],
      });
      return;
    }

    const existingVariable = globalVariables.find(
      (variable) => variable.name === variableName,
    );

    const onSuccessHandler = () => {
      setSuccessData({
        title: `${selectedProvider.provider} Activated`,
      });
      queryClient.invalidateQueries({ queryKey: ["useGetModelProviders"] });
      queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] });
      queryClient.invalidateQueries({ queryKey: ["useGetGlobalVariables"] });
      queryClient.invalidateQueries({ queryKey: ["useGetDefaultModel"] });
      queryClient.refetchQueries({ queryKey: ["flows"] });
      setSelectedProvider((prev) =>
        prev ? { ...prev, is_enabled: true } : null,
      );
      setIsEditing(false);
    };

    // For providers without API keys, we use a placeholder value
    const placeholderValue = "http://localhost:11434";

    if (existingVariable) {
      updateGlobalVariable(
        { id: existingVariable.id, value: placeholderValue },
        {
          onSuccess: onSuccessHandler,
          onError: (error: any) => {
            setErrorData({
              title: "Error Activating Provider",
              list: [
                error?.response?.data?.detail ||
                  "An unexpected error occurred. Please try again.",
              ],
            });
          },
        },
      );
    } else {
      createGlobalVariable(
        {
          name: variableName,
          value: placeholderValue,
          type: VARIABLE_CATEGORY.CREDENTIAL,
          category: VARIABLE_CATEGORY.GLOBAL,
          default_fields: [],
        },
        {
          onSuccess: onSuccessHandler,
          onError: (error: any) => {
            setErrorData({
              title: "Error Activating Provider",
              list: [
                error?.response?.data?.detail ||
                  "An unexpected error occurred. Please try again.",
              ],
            });
          },
        },
      );
    }
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

    // Check if variable already exists (provider is enabled)
    const existingVariable = globalVariables.find(
      (variable) => variable.name === variableName,
    );

    const onSuccessHandler = () => {
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
    };

    if (existingVariable) {
      // Update existing variable
      const oldApiKey = apiKey; // Store for potential rollback
      updateGlobalVariable(
        {
          id: existingVariable.id,
          value: apiKey,
        },
        {
          onSuccess: onSuccessHandler,
          onError: (error: any) => {
            // Revert to old API key on failure
            setApiKey(oldApiKey);
            setValidationFailed(true);
            setErrorData({
              title: "Error Updating API Key",
              list: [
                error?.response?.data?.detail ||
                  "An unexpected error occurred while updating the API key. Please try again.",
              ],
            });
          },
        },
      );
    } else {
      // Create new variable
      createGlobalVariable(
        {
          name: variableName,
          value: apiKey,
          type: VARIABLE_CATEGORY.CREDENTIAL,
          category: VARIABLE_CATEGORY.GLOBAL,
          default_fields: [],
        },
        {
          onSuccess: onSuccessHandler,
          onError: (error: any) => {
            setValidationFailed(true);
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
  };

  // Handle modal close - refresh if updates were made
  const handleClose = () => {
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <DialogContent className="flex flex-col overflow-hidden rounded-xl p-0 max-w-[768px] h-[560px] gap-0">
        {/* model provider header */}
        <DialogHeader className="flex w-full border-b px-4 py-3">
          <div className="flex justify-start items-center gap-3">
            {/* <ForwardedIconComponent name="Brain" className="w-5 h-5" /> */}
            <div className="text-[13px] font-semibold ">Model providers</div>
          </div>
        </DialogHeader>

        {/* model provider list */}
        <div className="flex flex-row w-full overflow-hidden">
          <div
            className={cn(
              "flex border-r p-2 flex-col transition-all duration-300 h-[513px] ease-in-out",
              selectedProvider ? "w-1/3" : "w-full",
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
                ? "w-2/3 opacity-100 translate-x-0"
                : "w-0 opacity-0 translate-x-full",
            )}
          >
            {" "}
            <div className="flex flex-col gap-1 p-4">
              <div className="flex flex-row gap-1 min-w-[300px]">
                {/* <ForwardedIconComponent
                  name={selectedProvider?.icon || 'Bot'}
                  className={cn(
                    'w-5 h-5 flex-shrink-0 transition-all',
                    !selectedProvider?.is_enabled && 'grayscale opacity-50'
                  )}
                /> */}
                <span className="text-[13px] font-semibold mr-auto">
                  {selectedProvider?.provider || "Unknown Provider"}
                  {requiresApiKey && " API Key"}
                  {requiresApiKey && (
                    <span className="text-red-500 ml-1">*</span>
                  )}
                </span>
              </div>
              <span className="text-[13px] text-muted-foreground  pt-1 pb-2">
                {requiresApiKey ? (
                  <>
                    Add your{" "}
                    <span className="underline cursor-pointer hover:text-primary">
                      {selectedProvider?.provider} API key
                    </span>{" "}
                    to enable these models
                  </>
                ) : (
                  <>
                    Activate {selectedProvider?.provider} to enable these models
                  </>
                )}
              </span>
              {requiresApiKey ? (
                <Input
                  placeholder="Add API key"
                  value={apiKey}
                  type="password"
                  onChange={(e) => {
                    isUserInputRef.current = true;
                    setValidationFailed(false);
                    setApiKey(e.target.value);
                  }}
                  endIcon={
                    isPending
                      ? "LoaderCircle"
                      : validationFailed
                        ? "X"
                        : selectedProvider?.is_enabled
                          ? "Check"
                          : undefined
                  }
                  endIconClassName={cn(
                    isPending && "animate-spin text-muted-foreground top-2.5",
                    validationFailed && "text-red-500",
                    !isPending &&
                      !validationFailed &&
                      selectedProvider?.is_enabled &&
                      "text-green-500",
                  )}
                />
              ) : (
                <Button
                  onClick={handleActivateNoApiKeyProvider}
                  loading={isPending}
                  disabled={selectedProvider?.is_enabled}
                >
                  {selectedProvider?.is_enabled
                    ? `${selectedProvider?.provider} Activated`
                    : `Activate ${selectedProvider?.provider}`}
                </Button>
              )}
            </div>
            {/* {selectedProvider?.is_enabled && (
                <Button
                  variant="menu"
                  size="icon"
                  unstyled
                  onClick={() => setIsEditing(!isEditing)}
                  className=""
                >
                  <ForwardedIconComponent
                    name={'Pencil'}
                    className={cn(
                      'h-4 w-4 flex-shrink-0 ',
                      !isEditing
                        ? 'text-primary hover:text-muted-foreground'
                        : 'text-muted-foreground hover:text-primary'
                    )}
                  />
                </Button>
              )} */}
            {/* model provider selection */}
            <div className="overflow-x-hidden ">
              <div
                className={cn(
                  "flex flex-col px-4 pb-4 gap-3 transition-all duration-300 ease-in-out",
                )}
              >
                <ModelSelection
                  modelType={modeltype}
                  availableModels={selectedProvider?.models || []}
                  onModelToggle={handleModelToggle}
                  providerName={selectedProvider?.provider}
                  isEnabledModel={selectedProvider?.is_enabled}
                />
              </div>

              {/* Edit */}
              {/* <div
                className={cn(
                  'flex flex-col transition-all duration-300 ease-in-out h-[403px]',
                  isEditing
                    ? 'opacity-100 translate-x-0'
                    : 'opacity-0 translate-x-full absolute inset-0'
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
                <ModelProviderActive
                  activeLLMs={activeLLMNames}
                  activeEmbeddings={activeEmbeddingNames}
                />
              </div> */}
            </div>
            {/* model provider footer */}
            {/* {isEditing && (
              <div className="flex justify-end border-t p-4 min-w-[300px] gap-2">
                <Button
                  className="w-full"
                  onClick={handleConfigureProvider}
                  loading={isPending}
                >
                  Configure
                </Button>
              </div>
            )} */}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ModelProviderModal;
