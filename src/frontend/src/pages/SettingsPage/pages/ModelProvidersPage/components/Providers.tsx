import { useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { PROVIDER_VARIABLE_MAPPING } from "@/constants/providerConstants";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useUpdateEnabledModels } from "@/controllers/API/queries/models/use-update-enabled-models";
import {
  useDeleteGlobalVariables,
  useGetGlobalVariables,
} from "@/controllers/API/queries/variables";
import ApiKeyModal from "@/modals/apiKeyModal";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { useQueryClient } from "@tanstack/react-query";

type Provider = {
  provider: string;
  icon?: string;
  is_enabled: boolean;
  model_count?: number;
  models?: { model_name: string; metadata: Record<string, any> }[];
};

const Providers = ({
  type,
  showExperimental,
}: {
  type: "enabled" | "available";
  showExperimental: boolean;
}) => {
  const { data: providersData = [], isLoading } = useGetModelProviders(
    {
      includeDeprecated: showExperimental,
      includeUnsupported: showExperimental,
    },
    {},
  );
  const queryClient = useQueryClient();
  const { data: enabledModelsData } = useGetEnabledModels();
  const { mutate: mutateUpdateEnabledModels } = useUpdateEnabledModels();
  const { data: globalVariables } = useGetGlobalVariables();
  const { mutate: mutateDeleteGlobalVariable } = useDeleteGlobalVariables();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const [openApiKeyDialog, setOpenApiKeyDialog] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [providerToDelete, setProviderToDelete] = useState<string | null>(null);

  const handleToggleModel = (
    providerName: string,
    modelName: string,
    enabled: boolean,
  ) => {
    mutateUpdateEnabledModels(
      {
        updates: [
          {
            provider: providerName,
            model_id: modelName,
            enabled: enabled,
          },
        ],
      },
      {
        onSuccess: () => {
          // Invalidate queries to refresh the UI
          queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] });
          setSuccessData({
            title: `${modelName} ${enabled ? "enabled" : "disabled"} successfully`,
          });
        },
        onError: () => {
          setErrorData({
            title: "Error updating model",
            list: ["Failed to update model status"],
          });
        },
      },
    );
  };

  const handleDeleteProvider = (providerName: string) => {
    if (!globalVariables) return;

    const variableName = PROVIDER_VARIABLE_MAPPING[providerName];
    if (!variableName) {
      setErrorData({
        title: "Error deleting provider",
        list: ["Provider variable mapping not found"],
      });
      return;
    }

    const variable = globalVariables.find((v) => v.name === variableName);
    if (!variable?.id) {
      setErrorData({
        title: "Error deleting provider",
        list: ["API key not found for this provider"],
      });
      return;
    }

    mutateDeleteGlobalVariable(
      { id: variable.id },
      {
        onSuccess: () => {
          setSuccessData({
            title: `${providerName} provider removed successfully`,
          });
          setDeleteDialogOpen(false);
          setProviderToDelete(null);
        },
        onError: () => {
          setErrorData({
            title: "Error deleting provider",
            list: ["Failed to remove API key"],
          });
        },
      },
    );
  };

  // Filter providers based on enabled status
  const filteredProviders: Provider[] = providersData
    .filter((provider) => {
      return type === "enabled" ? provider.is_enabled : !provider.is_enabled;
    })
    .map((provider) => ({
      provider: provider.provider,
      icon: provider.icon,
      is_enabled: provider.is_enabled,
      model_count: provider.models?.length || 0,
      models: provider.models || [],
    }));

  if (isLoading) {
    return <div className="text-muted-foreground">Loading providers...</div>;
  }

  return (
    <>
      <div>
        <h2 className="text-muted-foreground text-sm--medium">
          {type.charAt(0).toUpperCase() + type.slice(1)}
        </h2>
        <Accordion type="multiple">
          {filteredProviders.map((provider) => (
            <AccordionItem
              key={provider.provider}
              value={provider.provider}
              className="border-b-0"
            >
              <div
                className={cn(
                  "flex items-center my-2 py-1 relative hover:bg-transparent",
                )}
              >
                <ForwardedIconComponent
                  name={provider.icon || "Bot"}
                  className="w-4 h-4 mx-3"
                />

                <AccordionTrigger
                  className={cn(
                    "flex-1 py-0 hover:no-underline hover:bg-transparent",
                    provider.model_count && provider.model_count > 0
                      ? ""
                      : "pointer-events-none",
                  )}
                  disabled={!provider.model_count || provider.model_count === 0}
                >
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold pl-1 truncate">
                      {provider.provider}
                    </h3>
                    {provider.model_count && (
                      <p
                        className={cn(
                          "text-muted-foreground pr-2",
                          type === "enabled" &&
                            "text-accent-emerald-foreground",
                        )}
                      >
                        {provider.model_count}{" "}
                        {provider.model_count === 1 ? "model" : "models"}
                      </p>
                    )}
                  </div>
                </AccordionTrigger>

                <div className="flex items-center ml-auto">
                  {type === "enabled" ? (
                    <DeleteConfirmationModal
                      open={
                        deleteDialogOpen &&
                        providerToDelete === provider.provider
                      }
                      setOpen={(open) => {
                        setDeleteDialogOpen(open);
                        if (!open) setProviderToDelete(null);
                      }}
                      onConfirm={(e) => {
                        e.stopPropagation();
                        if (providerToDelete) {
                          handleDeleteProvider(providerToDelete);
                        }
                      }}
                      description={`access to ${provider.provider}`}
                      note="You can re-enable this provider at any time by adding your API key again"
                    >
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          setProviderToDelete(provider.provider);
                          setDeleteDialogOpen(true);
                        }}
                        className="p-2"
                      >
                        <ForwardedIconComponent
                          name="Trash"
                          className="text-destructive"
                        />
                      </Button>
                    </DeleteConfirmationModal>
                  ) : (
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenApiKeyDialog(true);
                        setSelectedProvider(provider.provider);
                      }}
                      className="p-2"
                    >
                      <ForwardedIconComponent
                        name="Plus"
                        className="hover:text-primary text-muted-foreground"
                      />
                    </Button>
                  )}
                </div>
              </div>

              <AccordionContent>
                {provider.models && provider.models.length > 0 ? (
                  <div className="space-y-1">
                    {provider.models.map((model, index) => {
                      const isModelEnabled =
                        enabledModelsData?.enabled_models?.[provider.provider]?.[model.model_name] ??
                        true;
                      const isDeprecated = model.metadata.deprecated;
                      const isPreview = model.metadata.preview;
                      const isNotSupported = model.metadata.not_supported;

                      return (
                        <div
                          key={`${model.model_name}-${index}`}
                          className="flex items-center ml-3 gap-2"
                        >
                          {type === "enabled" ? (
                            <Checkbox
                              checked={isModelEnabled}
                              onCheckedChange={(checked) => {
                                handleToggleModel(
                                  provider.provider,
                                  model.model_name,
                                  checked as boolean,
                                );
                              }}
                            />
                          ) : (
                            <div className="mr-4" />
                          )}
                          <div
                            className={cn(
                              "text-sm py-1 pr-2 pl-1 font-medium",
                              !isModelEnabled && "text-muted-foreground",
                            )}
                          >
                            {model.model_name}
                          </div>

                          {isDeprecated && (
                            <Badge
                              variant="destructive"
                              className="text-xs px-2 py-0"
                            >
                              Deprecated
                            </Badge>
                          )}

                          {isPreview && (
                            <Badge
                              variant="outline"
                              className="text-xs px-2 py-0"
                            >
                              Preview
                            </Badge>
                          )}

                          {isNotSupported && (
                            <Badge
                              variant="secondary"
                              className="text-xs px-2 py-0"
                            >
                              Not Supported
                            </Badge>
                          )}

                          {model.metadata.reasoning && (
                            <div className="flex items-center space-x-1 text-muted-foreground">
                              •
                              <ForwardedIconComponent
                                name="Brain"
                                className="w-4 h-4 mx-1"
                              />
                              <span className="italic pr-2">Reasoning</span>
                            </div>
                          )}

                          {model.metadata.model_type === "embeddings" && (
                            <div className="flex items-center space-x-1 text-muted-foreground">
                              •
                              <ForwardedIconComponent
                                name="Layers"
                                className="w-4 h-4 mx-1"
                              />
                              <span className="italic pr-2">Embedding</span>
                            </div>
                          )}

                          {model.metadata.tool_calling && (
                            <div className="flex items-center space-x-1 text-muted-foreground">
                              <span className="text-muted-foreground"> • </span>
                              <ForwardedIconComponent
                                name="Hammer"
                                className="w-4 h-4 mx-1"
                              />
                              <span className="italic pr-2">Tooling</span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="ml-12 text-sm text-muted-foreground py-1 px-2">
                    No models available
                  </div>
                )}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
      <ApiKeyModal
        open={openApiKeyDialog}
        onClose={() => setOpenApiKeyDialog(false)}
        provider={selectedProvider || "Provider"}
      />
    </>
  );
};

export default Providers;
