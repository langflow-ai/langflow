import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface LLMModel {
  name: string;
  provider: string;
  icon: string;
  metadata: Record<string, any>;
}

export interface LLMModelsResponse {
  models: LLMModel[];
  enabledProviders: string[];
}

/**
 * Hook to fetch only enabled LLM models (excludes embeddings and disabled models/providers)
 */
export const useGetLLMModels: useQueryFunctionType<
  undefined,
  LLMModelsResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getLLMModelsFn = async (): Promise<LLMModelsResponse> => {
    try {
      // Fetch LLM models only (model_type=llm excludes embeddings)
      const response = await api.get<any[]>(
        `${getURL("MODELS")}?model_type=llm`,
      );
      const providersData = response.data;

      const models: LLMModel[] = [];
      const enabledProviders: string[] = [];

      for (const provider of providersData) {
        // Only include enabled providers
        if (!provider.is_enabled) continue;

        enabledProviders.push(provider.provider);
        const icon = getProviderIcon(provider.provider);

        for (const model of provider.models || []) {
          // Filter out deprecated and unsupported models
          const metadata = model.metadata || {};
          if (metadata.deprecated || metadata.not_supported) continue;

          // Only include default models (first 5 per provider) or explicitly enabled
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
      console.error("Error fetching LLM models:", error);
      return { models: [], enabledProviders: [] };
    }
  };

  const queryResult = query(["useGetLLMModels"], getLLMModelsFn, {
    refetchOnWindowFocus: false,
    staleTime: 1000 * 60 * 5, // 5 minutes
    ...options,
  });

  return queryResult;
};

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
