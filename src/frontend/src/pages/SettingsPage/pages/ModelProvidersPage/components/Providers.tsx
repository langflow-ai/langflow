import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import ApiKeyModal from "@/modals/apiKeyModal";
import { cn } from "@/utils/utils";
import { useState } from "react";

type Provider = {
  provider: string;
  icon?: string;
  is_enabled: boolean;
  model_count?: number;
};

const Providers = ({ type }: { type: "enabled" | "available" }) => {
  const { data: providersData = [], isLoading } = useGetModelProviders();
  const [openApiKeyDialog, setOpenApiKeyDialog] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);

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
                {provider.model_count} {provider.model_count === 1 ? 'model' : 'models'}
              </p>
            )}
          </div>
          <div className="flex items-center ml-auto">
            <Button
              size="icon"
              variant="ghost"
              onClick={(e) => {
                e.stopPropagation();
                if (type === "available") {
                  setOpenApiKeyDialog(true);
                  setSelectedProvider(provider.provider);
                }
              }}
              className={cn(
                "p-2",
                type === "available" && "group-hover:bg-transparent",
              )}
            >
              <ForwardedIconComponent
                name={type === "enabled" ? "Trash" : "Plus"}
                className={cn(
                  "text-destructive",
                  type === "available" && "group-hover:text-primary text-muted-foreground",
                )}
              />
            </Button>
          </div>
        </div>
      ))}
    </div>
    <ApiKeyModal
      open={openApiKeyDialog}
      onClose={() => setOpenApiKeyDialog(false)}
      provider={selectedProvider || "Provider"}
      onSave={() => {}}
    />
    </>
  );
};

export default Providers;
