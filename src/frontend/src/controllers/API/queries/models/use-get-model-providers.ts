import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ModelProviderInfo {
  provider: string;
  models: Array<{
    model_name: string;
    metadata: Record<string, unknown>;
  }>;
  is_enabled: boolean;
  is_configured?: boolean;
  api_docs_url?: string;
  /** Icon name from provider metadata (e.g. MODEL_PROVIDER_METADATA). */
  icon?: string;
}

export interface ModelProviderWithStatus extends ModelProviderInfo {
  icon?: string;
}

export interface GetModelProvidersParams {
  includeDeprecated?: boolean;
  includeUnsupported?: boolean;
}

export const useGetModelProviders: useQueryFunctionType<
  GetModelProvidersParams | undefined,
  ModelProviderWithStatus[]
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getModelProvidersFn = async (): Promise<ModelProviderWithStatus[]> => {
    // Build query params
    const queryParams = new URLSearchParams();
    if (params?.includeDeprecated) {
      queryParams.append("include_deprecated", "true");
    }
    if (params?.includeUnsupported) {
      queryParams.append("include_unsupported", "true");
    }

    const url = `${getURL("MODELS")}${
      queryParams.toString() ? `?${queryParams.toString()}` : ""
    }`;

    // Fetch the models with provider information including is_enabled status from server
    // Let errors propagate so React Query can retry and preserve stale data
    const response = await api.get<ModelProviderInfo[]>(url);
    const providersData = response.data;

    return providersData.map((providerInfo) => ({
      ...providerInfo,
      // Prefer backend metadata icon so new providers don't need a frontend map
      // entry; fall back to the legacy name→asset map, then Bot.
      icon: providerInfo.icon || getProviderIcon(providerInfo.provider),
    }));
  };

  const queryResult = query(
    [
      "useGetModelProviders",
      params?.includeDeprecated,
      params?.includeUnsupported,
    ],
    getModelProvidersFn,
    {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 5, // 5 minutes
      ...options,
    },
  );

  return queryResult;
};

// Helper function to map provider names to icon names when the API omits icon.
const getProviderIcon = (providerName: string): string => {
  const iconMap: Record<string, string> = {
    OpenAI: "OpenAI",
    Anthropic: "Anthropic",
    "Google Generative AI": "GoogleGenerativeAI",
    Groq: "Groq",
    "Amazon Bedrock": "Bedrock",
    NVIDIA: "NVIDIA",
    Cohere: "Cohere",
    // Both Azure providers share the Azure brand icon asset (there is no
    // AzureOpenAI icon module in the frontend icon registry).
    "Azure OpenAI": "Azure",
    "Azure AI Foundry": "Azure",
    SambaNova: "SambaNova",
    Ollama: "Ollama",
    "IBM WatsonX": "IBM",
    "IBM watsonx.ai": "IBM",
    OpenRouter: "OpenRouter",
    "OpenAI Compatible": "Plug",
  };

  return iconMap[providerName] || "Bot";
};
