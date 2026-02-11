import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface EmbeddingModel {
  name: string;
  provider: string;
  icon: string;
  metadata: Record<string, any>;
}

export interface EmbeddingModelsResponse {
  models: EmbeddingModel[];
  enabledProviders: string[];
}

// Helper function to map provider names to icon names
const getProviderIcon = (providerName: string): string => {
  const iconMap: Record<string, string> = {
    OpenAI: "OpenAI",
    Anthropic: "Anthropic",
    "Google Generative AI": "GoogleGenerativeAI",
    Groq: "Groq",
    "Amazon Bedrock": "Bedrock",
    NVIDIA: "NVIDIA",
    Cohere: "Cohere",
    "Azure OpenAI": "AzureOpenAI",
    SambaNova: "SambaNova",
    Ollama: "Ollama",
    "IBM WatsonX": "IBM",
    "IBM watsonx.ai": "IBM",
  };

  return iconMap[providerName] || "Bot";
};

/**
 * Hook to fetch only enabled embedding models (model_type=embeddings)
 */
export const useGetEmbeddingModels: useQueryFunctionType<
  undefined,
  EmbeddingModelsResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getEmbeddingModelsFn = async (): Promise<EmbeddingModelsResponse> => {
    try {
      const response = await api.get<any[]>(
        `${getURL("MODELS")}?model_type=embeddings`,
      );
      const providersData = response.data;

      const models: EmbeddingModel[] = [];
      const enabledProviders: string[] = [];

      for (const provider of providersData) {
        if (!provider.is_enabled) continue;

        enabledProviders.push(provider.provider);
        const icon = getProviderIcon(provider.provider);

        for (const model of provider.models || []) {
          const metadata = model.metadata || {};
          if (metadata.deprecated || metadata.not_supported) continue;
          if (!metadata.default) continue;

          models.push({
            name: model.model_name,
            provider: provider.provider,
            icon,
            metadata,
          });
        }
      }

      return { models, enabledProviders };
    } catch (error) {
      console.error("Error fetching embedding models:", error);
      return { models: [], enabledProviders: [] };
    }
  };

  const queryResult = query(
    ["useGetEmbeddingModels"],
    getEmbeddingModelsFn,
    {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 5,
      ...options,
    },
  );

  return queryResult;
};
