import { PROVIDER_VARIABLE_MAPPING } from "@/constants/providerConstants";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { useGetGlobalVariables } from "../variables";

export interface ModelProviderInfo {
  provider: string;
  models: Array<{
    model_name: string;
    metadata: Record<string, any>;
  }>;
}

export interface ModelProviderWithStatus extends ModelProviderInfo {
  is_enabled: boolean;
  icon?: string;
}

export const useGetModelProviders: useQueryFunctionType<
  undefined,
  ModelProviderWithStatus[]
> = (options) => {
  const { query } = UseRequestProcessor();
  const { data: globalVariables = [] } = useGetGlobalVariables();

  const getModelProvidersFn = async (): Promise<ModelProviderWithStatus[]> => {
    try {
      // Fetch the models with provider information
      const response = await api.get<ModelProviderInfo[]>(getURL("MODELS"));
      const providersData = response.data;

      // Check which providers are enabled by looking for their API keys in global variables
      const globalVariableNames = new Set(globalVariables.map((v) => v.name));

      return providersData.map((providerInfo) => {
        const normalized =
          providerInfo.provider === "Google" ? "Google Generative AI" : providerInfo.provider;
        const variableName = PROVIDER_VARIABLE_MAPPING[normalized];
        const is_enabled = variableName
          ? globalVariableNames.has(variableName)
          : false;

        return {
          ...providerInfo,
          is_enabled,
          icon: getProviderIcon(providerInfo.provider),
        };
      });
    } catch (error) {
      console.error("Error fetching model providers:", error);
      return [];
    }
  };

  const queryResult = query(
    ["useGetModelProviders", globalVariables],
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
