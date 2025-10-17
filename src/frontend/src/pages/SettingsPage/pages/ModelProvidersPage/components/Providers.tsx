import { useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import ApiKeyModal from "@/modals/apiKeyModel";
import { RemoveProviderModal } from "@/modals/removeProviderModal";
import { cn } from "@/utils/utils";

type ProviderData = {
  provider: string;
  icon?: string;
  is_enabled: boolean;
  models: string[];
  api_key?: string;
};

type Provider = {
  provider: string;
  icon?: string;
  is_enabled: boolean;
  model_count?: number;
};

const Providers = ({ type }: { type: "enabled" | "available" }) => {
  const [openApiKeyDialog, setOpenApiKeyDialog] = useState(false);
  const [openConfirmDialog, setOpenConfirmDialog] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const [providersData, setProvidersData] = useState<ProviderData[]>([
    {
      provider: "OpenAI",
      icon: "OpenAI",
      is_enabled: true,
      models: ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    {
      provider: "Anthropic",
      icon: "Anthropic",
      is_enabled: true,
      models: [
        "claude-3-opus",
        "claude-3-sonnet",
        "claude-3-haiku",
        "claude-3-7-sonnet-latest",
        "claude-3-5-haiku-latest",
      ],
    },
    {
      provider: "Google",
      icon: "Google",
      is_enabled: false,
      models: [],
    },
    {
      provider: "Azure OpenAI",
      icon: "Azure",
      is_enabled: false,
      models: [],
    },
    {
      provider: "Cohere",
      icon: "Cohere",
      is_enabled: false,
      models: [],
    },
    {
      provider: "Hugging Face",
      icon: "HuggingFace",
      is_enabled: false,
      models: [],
    },
    {
      provider: "Mistral",
      icon: "Mistral",
      is_enabled: false,
      models: [],
    },
    {
      provider: "Groq",
      icon: "Groq",
      is_enabled: true,
      models: ["llama2-70b", "mixtral-8x7b"],
    },
  ]);

  const handleAddProvider = (providerName: string, apiKey: string) => {
    // Mock model data for each provider - replace with real API call later
    const mockModels: Record<string, string[]> = {
      OpenAI: ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
      Anthropic: ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
      Google: ["gemini-pro", "gemini-pro-vision"],
      "Azure OpenAI": ["gpt-4", "gpt-35-turbo"],
      Cohere: ["command", "command-light"],
      "Hugging Face": ["mistralai/Mistral-7B-v0.1"],
      Mistral: ["mistral-tiny", "mistral-small", "mistral-medium"],
      Groq: ["llama2-70b", "mixtral-8x7b"],
    };

    setProvidersData((prev) =>
      prev.map((p) =>
        p.provider === providerName
          ? {
              ...p,
              is_enabled: true,
              api_key: apiKey,
              models: mockModels[providerName] || [],
            }
          : p,
      ),
    );
    setOpenApiKeyDialog(false);
    setSelectedProvider(null);
  };

  const handleRemoveProvider = (providerName: string) => {
    setProvidersData((prev) =>
      prev.map((p) =>
        p.provider === providerName
          ? { ...p, is_enabled: false, api_key: undefined, models: [] }
          : p,
      ),
    );
  };

  const handleRemoveClick = (providerName: string) => {
    setSelectedProvider(providerName);
    setOpenConfirmDialog(true);
  };

  const handleAddClick = (providerName: string) => {
    setSelectedProvider(providerName);
    setOpenApiKeyDialog(true);
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
                handleAddClick(provider.provider);
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
              {type === "enabled" && (provider.model_count ?? 0) > 0 && (
                <p className="text-accent-emerald-foreground">
                  {provider.model_count}{" "}
                  {provider.model_count === 1 ? "model" : "models"}
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
                    handleAddClick(provider.provider);
                  } else {
                    handleRemoveClick(provider.provider);
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
                    type === "available" &&
                      "group-hover:text-primary text-muted-foreground",
                  )}
                />
              </Button>
            </div>
          </div>
        ))}
      </div>
      <ApiKeyModal
        open={openApiKeyDialog}
        onClose={() => {
          setOpenApiKeyDialog(false);
          setSelectedProvider(null);
        }}
        provider={selectedProvider || "Provider"}
        onSave={(apiKey: string) => {
          if (selectedProvider) {
            handleAddProvider(selectedProvider, apiKey);
          }
        }}
      />
      <RemoveProviderModal
        open={openConfirmDialog}
        setOpen={setOpenConfirmDialog}
        providerName={selectedProvider || ""}
        onConfirm={() => {
          if (selectedProvider) {
            handleRemoveProvider(selectedProvider);
          }
        }}
        onClose={() => setSelectedProvider(null)}
      />
    </>
  );
};

export default Providers;
