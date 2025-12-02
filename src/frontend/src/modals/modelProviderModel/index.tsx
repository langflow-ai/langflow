import { useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import ProviderList from "@/pages/SettingsPage/pages/ModelProvidersPage/components/provider-list";
import {
  Model,
  Provider,
} from "@/pages/SettingsPage/pages/ModelProvidersPage/components/types";
import { useProviderActions } from "@/pages/SettingsPage/pages/ModelProvidersPage/components/use-provider-actions";
import { cn } from "@/utils/utils";

interface ModelProviderModalProps {
  open: boolean;
  onClose: () => void;
  hasEnabledModels: boolean;
}

const ModelProviderModal = ({
  open,
  onClose,
  hasEnabledModels,
}: ModelProviderModalProps) => {
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null,
  );
  const { data: enabledModelsData } = useGetEnabledModels();
  const { handleToggleModel } = useProviderActions();
  const [isEditing, setIsEditing] = useState(true);

  // Separate models into LLM and Embedding categories
  const { llmModels, embeddingModels } = useMemo(() => {
    if (!selectedProvider?.models) {
      return { llmModels: [], embeddingModels: [] };
    }
    const llm: Model[] = [];
    const embedding: Model[] = [];
    selectedProvider.models.forEach((model) => {
      const modelType = model.metadata?.model_type || "llm";
      if (modelType === "embeddings") {
        embedding.push(model);
      } else {
        llm.push(model);
      }
    });
    return { llmModels: llm, embeddingModels: embedding };
  }, [selectedProvider?.models]);

  // Get enabled state for a model
  const isModelEnabled = (modelName: string): boolean => {
    if (!selectedProvider) return false;
    const providerModels =
      enabledModelsData?.enabled_models?.[selectedProvider.provider];
    if (providerModels === undefined) return false;
    const isEnabled = providerModels[modelName];
    // If no explicit value, check if model has default enabled in metadata
    if (isEnabled === undefined) {
      const model = selectedProvider.models?.find(
        (m) => m.model_name === modelName,
      );
      return model?.metadata?.default === true;
    }
    return isEnabled === true;
  };

  const handleModelToggle = (modelName: string, enabled: boolean) => {
    if (!selectedProvider) return;
    handleToggleModel(selectedProvider.provider, modelName, enabled);
  };

  const handleProviderSelect = (provider: Provider) => {
    setSelectedProvider((prev) =>
      prev?.provider === provider.provider ? null : provider,
    );
    setIsEditing(!provider.is_enabled);
  };

  // Get list of active models for the editing panel badges
  const numberOfActiveLLMs = useMemo(() => {
    return llmModels
      .filter((m) => isModelEnabled(m.model_name))
      .map((m) => m.model_name);
  }, [llmModels, enabledModelsData, selectedProvider]);

  const numberOfActiveEmbeddings = useMemo(() => {
    return embeddingModels
      .filter((m) => isModelEnabled(m.model_name))
      .map((m) => m.model_name);
  }, [embeddingModels, enabledModelsData, selectedProvider]);

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="flex flex-col overflow-hidden rounded-xl p-0 max-w-[950px] gap-0">
        <DialogHeader className="flex w-full border-b px-4 py-3">
          <div className="flex justify-start items-center gap-3">
            <ForwardedIconComponent name="Brain" className="w-5 h-5" />
            <div className="text-[13px] font-semibold ">Model providers</div>
          </div>
        </DialogHeader>
        <div className="flex flex-row w-full overflow-hidden">
          <div
            className={cn(
              "flex border-r p-2 flex-col transition-all duration-300 ease-in-out",
              selectedProvider ? "w-1/2" : "w-full",
            )}
          >
            <ProviderList
              onProviderSelect={handleProviderSelect}
              selectedProviderName={selectedProvider?.provider ?? null}
            />
          </div>
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

            <div className="relative overflow-x-hidden min-w-[300px] ">
              <div
                className={cn(
                  "flex flex-col p-4 gap-3 transition-all duration-300 ease-in-out min-h-[480px] h-[480px]",
                  isEditing
                    ? "opacity-0 -translate-x-full absolute inset-0"
                    : "opacity-100 translate-x-0",
                )}
              >
                {llmModels.length > 0 && (
                  <>
                    <div className="text-[13px] font-semibold text-muted-foreground">
                      LLM
                    </div>
                    {llmModels.map((model) => {
                      const enabled = isModelEnabled(model.model_name);
                      return (
                        <div
                          key={model.model_name}
                          className="flex flex-row items-center justify-between"
                        >
                          <div className="flex flex-row items-center gap-2">
                            <ForwardedIconComponent
                              name={model.metadata?.icon || "Bot"}
                              className="w-5 h-5"
                            />
                            <span className="text-sm">{model.model_name}</span>
                          </div>
                          <Switch
                            checked={enabled}
                            onCheckedChange={(checked) =>
                              handleModelToggle(model.model_name, checked)
                            }
                          />
                        </div>
                      );
                    })}
                  </>
                )}
                {embeddingModels.length > 0 && (
                  <>
                    <div className="text-[13px] font-semibold text-muted-foreground pt-2">
                      Embedding
                    </div>
                    {embeddingModels.map((model) => {
                      const enabled = isModelEnabled(model.model_name);
                      return (
                        <div
                          key={model.model_name}
                          className="flex flex-row items-center justify-between"
                        >
                          <div className="flex flex-row items-center gap-2">
                            <ForwardedIconComponent
                              name={model.metadata?.icon || "Bot"}
                              className="w-5 h-5"
                            />
                            <span className="text-sm">{model.model_name}</span>
                          </div>
                          <Switch
                            checked={enabled}
                            onCheckedChange={(checked) =>
                              handleModelToggle(model.model_name, checked)
                            }
                          />
                        </div>
                      );
                    })}
                  </>
                )}
              </div>
              <div
                className={cn(
                  "flex flex-col transition-all duration-300 ease-in-out",
                  isEditing
                    ? "opacity-100 translate-x-0"
                    : "opacity-0 translate-x-full absolute inset-0",
                )}
              >
                <div className="flex flex-col gap-4 p-4">
                  <div className="text-[13px] -mb-1 font-medium flex items-center gap-1">
                    Authorization Name
                    <ForwardedIconComponent
                      name="info"
                      className="w-4 h-4 text-muted-foreground ml-1"
                    />
                  </div>
                  <Input placeholder="Authorization Name" />
                  <div className="text-[13px] -mb-1 font-medium flex items-center gap-1">
                    API Key
                    <ForwardedIconComponent
                      name="info"
                      className="w-4 h-4 text-muted-foreground ml-1"
                    />
                  </div>
                  <Input placeholder="API Key" />
                  <div className="text-muted-foreground text-xs flex items-center gap-1 -mt-1 hover:underline cursor-pointer w-fit">
                    Find your API key{" "}
                    <ForwardedIconComponent
                      name="external-link"
                      className="w-4 h-4"
                    />
                  </div>
                  <div className="text-[13px] -mb-1 font-medium flex items-center gap-1">
                    API Base
                    <ForwardedIconComponent
                      name="info"
                      className="w-4 h-4 text-muted-foreground ml-1"
                    />{" "}
                  </div>
                  <Input placeholder="API Base" />
                </div>
                <div className="flex flex-col p-4 border-t overflow-y-auto h-[178.5px]">
                  <div className="text-[13px] font-medium">Models</div>
                  {numberOfActiveLLMs.length > 0 && (
                    <div className="pt-4">
                      <div className="text-[10px] text-muted-foreground">
                        LLM
                      </div>
                      <div className="flex flex-row gap-2 mt-2 flex-wrap">
                        {numberOfActiveLLMs.map((model) => (
                          <Badge
                            key={model}
                            variant="secondaryStatic"
                            size="sq"
                            className="whitespace-nowrap"
                          >
                            {model}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {numberOfActiveEmbeddings.length > 0 && (
                    <>
                      <div className="text-[10px] pt-4 text-muted-foreground">
                        Embeddings
                      </div>
                      <div className="flex flex-row gap-2 mt-2 flex-wrap">
                        {numberOfActiveEmbeddings.map((model) => (
                          <Badge
                            key={model}
                            variant="secondaryStatic"
                            size="sq"
                            className="whitespace-nowrap"
                          >
                            {model}
                          </Badge>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
            <div className="flex justify-end border-t p-4 min-w-[300px] gap-2">
              {selectedProvider?.is_enabled && (
                <Button variant="ghost" className="w-full">
                  Cancel
                </Button>
              )}
              <Button className="w-full">
                {selectedProvider?.is_enabled ? "Update" : "Configure"}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ModelProviderModal;
