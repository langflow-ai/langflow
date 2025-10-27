import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ModelProviderInfo {
  provider: string;
  models: Array<{
    model_name: string;
    metadata: Record<string, any>;
  }>;
  is_enabled: boolean;
}

export interface ModelProviderWithStatus extends ModelProviderInfo {
  icon?: string;
}

export const useGetModelProviders: useQueryFunctionType<
  undefined,
  ModelProviderWithStatus[]
> = (options) => {
  const { query } = UseRequestProcessor();

  const getModelProvidersFn = async (): Promise<ModelProviderWithStatus[]> => {
    try {
      // Fetch the models with provider information including is_enabled status from server
      const response = await api.get<ModelProviderInfo[]>(getURL("MODELS"));
      const providersData = response.data;

      return providersData.map((providerInfo) => ({
        ...providerInfo,
        icon: getProviderIcon(providerInfo.provider),
      }));
    } catch (error) {
      console.error("Error fetching model providers:", error);
      return [];
    }
  };

  const queryResult = query(
    ["useGetModelProviders"],
    getModelProvidersFn,
    {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 5, // 5 minutes
      ...options,
    },
  );

  return queryResult;
};

// Helper function to map provider names to icon names
const getProviderIcon = (providerName: string): string => {
  const iconMap: Record<string, string> = {
    OpenAI: "OpenAI",
    Anthropic: "Anthropic",
    "Google Generative AI": "Google",
    Groq: "Groq",
    "Amazon Bedrock": "Bedrock",
    NVIDIA: "NVIDIA",
    Cohere: "Cohere",
    "Azure OpenAI": "AzureOpenAI",
    SambaNova: "SambaNova",
    Ollama: "Ollama",
  };

  return iconMap[providerName] || "Bot";
};
