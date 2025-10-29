import { useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { PROVIDER_VARIABLE_MAPPING } from "@/constants/providerConstants";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import {
  useDeleteGlobalVariables,
  useGetGlobalVariables,
} from "@/controllers/API/queries/variables";
import ApiKeyModal from "@/modals/apiKeyModal";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";

type Provider = {
  provider: string;
  icon?: string;
  is_enabled: boolean;
  model_count?: number;
};

const Providers = ({ type }: { type: "enabled" | "available" }) => {
  const { data: providersData = [], isLoading } = useGetModelProviders();
  const { data: globalVariables } = useGetGlobalVariables();
  const { mutate: mutateDeleteGlobalVariable } = useDeleteGlobalVariables();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const [openApiKeyDialog, setOpenApiKeyDialog] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [providerToDelete, setProviderToDelete] = useState<string | null>(null);

  console.log("Providers data:", providersData);

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
        {filteredProviders.map((provider) => (
          <div
            key={provider.provider}
            onClick={() => {
              if (type === "available") {
                setOpenApiKeyDialog(true);
                setSelectedProvider(provider.provider);
              }
            }}
            className={cn(
              "flex items-center my-2 py-1 group ",
              type === "available" &&
                "hover:bg-muted hover:rounded-md cursor-pointer",
            )}
          >
            <ForwardedIconComponent
              name={provider.icon || "Bot"}
              className="w-4 h-4 mx-3"
            />

            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold pl-1 truncate">
                {provider.provider}
              </h3>
              {type === "enabled" && provider.model_count && (
                <p className="text-accent-emerald-foreground">
                  {provider.model_count}{" "}
                  {provider.model_count === 1 ? "model" : "models"}
                </p>
              )}
            </div>
            <div className="flex items-center ml-auto">
              {type === "enabled" ? (
                <DeleteConfirmationModal
                  open={
                    deleteDialogOpen && providerToDelete === provider.provider
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
                  className="p-2 group-hover:bg-transparent"
                >
                  <ForwardedIconComponent
                    name="Plus"
                    className="group-hover:text-primary text-muted-foreground"
                  />
                </Button>
              )}
            </div>
          </div>
        ))}
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
