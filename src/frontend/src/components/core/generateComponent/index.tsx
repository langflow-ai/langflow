import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { postGenerateComponentPromptStream } from "@/controllers/API/queries/generate-component";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { useAddComponent } from "@/hooks/use-add-component";
import useAlertStore from "@/stores/alertStore";
import { useDarkStore } from "@/stores/darkStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useGenerateComponentStore } from "@/stores/generateComponentStore";
import { createFlowComponent, getNodeId } from "@/utils/reactflowUtils";
import GenerateComponentTerminal from "./generate-component-terminal";
import type { AssistantConfigResponse, GenerateComponentPromptResponse, ProgressState, SubmitResult } from "./types";

function extractSubmitResult(response: GenerateComponentPromptResponse): SubmitResult {
  let content: string;
  if (response.result) {
    content = response.result;
  } else if (response.text) {
    content = response.text;
  } else if (response.exception_message) {
    throw new Error(response.exception_message);
  } else {
    content = JSON.stringify(response, null, 2);
  }

  const result: SubmitResult = { content };

  if (response.validated !== undefined) {
    result.validated = response.validated;
  }
  if (response.class_name) {
    result.className = response.class_name;
  }
  if (response.validation_error) {
    result.validationError = response.validation_error;
  }
  if (response.validation_attempts) {
    result.validationAttempts = response.validation_attempts;
  }
  if (response.component_code) {
    result.componentCode = response.component_code;
  }

  return result;
}

// Preferred providers in order of priority
const PREFERRED_PROVIDERS = ["Anthropic", "OpenAI", "Google Generative AI", "Groq"];

const GenerateComponent = memo(function GenerateComponent() {
  const isTerminalOpen = useGenerateComponentStore((state) => state.isTerminalOpen);
  const setTerminalOpen = useGenerateComponentStore((state) => state.setTerminalOpen);
  const maxRetries = useGenerateComponentStore((state) => state.maxRetries);
  const setMaxRetries = useGenerateComponentStore((state) => state.setMaxRetries);

  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const version = useDarkStore((state) => state.version);
  const [isLoading, setIsLoading] = useState(false);
  const { mutateAsync: validateComponentCode } = usePostValidateComponentCode();
  const navigate = useCustomNavigate();
  const addComponent = useAddComponent();
  const addFlow = useAddFlow();

  // Use the existing model providers hooks
  const { data: modelProviders, refetch: refetchProviders, isLoading: isProvidersLoading, isRefetching: isProvidersRefetching } = useGetModelProviders(
    { includeDeprecated: false, includeUnsupported: false },
    { enabled: isTerminalOpen }
  );
  const { data: enabledModelsData, refetch: refetchEnabledModels, isLoading: isEnabledLoading, isRefetching: isEnabledRefetching } = useGetEnabledModels(
    { enabled: isTerminalOpen }
  );
  const isConfigLoading = isProvidersLoading || isProvidersRefetching || isEnabledLoading || isEnabledRefetching;

  // Transform model providers data into the format expected by the terminal
  const configData = useMemo((): AssistantConfigResponse | undefined => {
    if (!modelProviders || !enabledModelsData) return undefined;

    const enabledModels = enabledModelsData.enabled_models || {};

    // Filter to only enabled providers with language models
    const enabledProviders = modelProviders.filter(p => p.is_enabled);
    const configuredProviderNames = enabledProviders.map(p => p.provider);

    // Build providers list with only ACTIVE models (toggled on by user)
    const providers = enabledProviders.map(provider => {
      const providerEnabledModels = enabledModels[provider.provider] || {};

      // Filter to language models that are ENABLED by user
      const activeModels = provider.models.filter(m => {
        const modelType = m.metadata?.model_type;
        const isLanguageModel = !modelType || modelType === "language" || modelType === "llm";
        const isEnabled = providerEnabledModels[m.model_name] === true;
        return isLanguageModel && isEnabled;
      });

      return {
        name: provider.provider,
        configured: true,
        default_model: activeModels[0]?.model_name || null,
        models: activeModels.map(m => ({
          name: m.model_name,
          display_name: m.metadata?.display_name || m.model_name,
        })),
      };
    }).filter(p => p.models.length > 0);

    // Determine default provider based on priority
    let defaultProvider: string | null = null;
    let defaultModel: string | null = null;

    for (const preferred of PREFERRED_PROVIDERS) {
      const provider = providers.find(p => p.name === preferred);
      if (provider) {
        defaultProvider = provider.name;
        defaultModel = provider.default_model;
        break;
      }
    }

    // Fallback to first provider
    if (!defaultProvider && providers.length > 0) {
      defaultProvider = providers[0].name;
      defaultModel = providers[0].default_model;
    }

    return {
      configured: configuredProviderNames.length > 0,
      configured_providers: configuredProviderNames,
      providers,
      default_provider: defaultProvider,
      default_model: defaultModel,
    };
  }, [modelProviders, enabledModelsData]);

  const isConfigured = configData?.configured ?? false;

  // Refetch providers every time terminal opens
  useEffect(() => {
    if (isTerminalOpen) {
      refetchProviders();
      refetchEnabledModels();
    }
  }, [isTerminalOpen, refetchProviders, refetchEnabledModels]);

  const handleCloseTerminal = useCallback(() => {
    setTerminalOpen(false);
  }, [setTerminalOpen]);

  const handleConfigureClick = useCallback(() => {
    navigate("/settings/model-providers");
  }, [navigate]);

  const handleSubmit = useCallback(
    async (
      input: string,
      provider?: string,
      modelName?: string,
      onProgress?: (progress: ProgressState) => void,
    ): Promise<SubmitResult> => {
      if (!currentFlowId) {
        throw new Error("No flow selected. Please open a flow first.");
      }

      setIsLoading(true);
      try {
        const response = await postGenerateComponentPromptStream({
          flowId: currentFlowId,
          inputValue: input,
          maxRetries,
          provider,
          modelName,
          onProgress,
        });

        return extractSubmitResult(response as GenerateComponentPromptResponse);
      } finally {
        setIsLoading(false);
      }
    },
    [currentFlowId, maxRetries],
  );

  const handleAddToCanvas = useCallback(
    async (code: string) => {
      const response = await validateComponentCode({
        code,
        frontend_node: undefined as never,
      });

      addComponent(response.data, response.type);
    },
    [validateComponentCode, addComponent],
  );

  const handleSaveToSidebar = useCallback(
    async (code: string, className: string) => {
      const response = await validateComponentCode({
        code,
        frontend_node: undefined as never,
      });

      const nodeId = getNodeId(response.type);
      const nodeData = {
        node: response.data,
        showNode: !response.data.minimized,
        type: response.type,
        id: nodeId,
      };

      const flowComponent = createFlowComponent(nodeData, version);
      await addFlow({ flow: flowComponent, override: false });
      setSuccessData({ title: `${className} saved to sidebar` });
    },
    [validateComponentCode, addFlow, version, setSuccessData],
  );

  return (
    <GenerateComponentTerminal
      isOpen={isTerminalOpen}
      onClose={handleCloseTerminal}
      onSubmit={handleSubmit}
      onAddToCanvas={handleAddToCanvas}
      onSaveToSidebar={handleSaveToSidebar}
      isLoading={isLoading}
      maxRetries={maxRetries}
      onMaxRetriesChange={setMaxRetries}
      isConfigured={isConfigured}
      isConfigLoading={isConfigLoading}
      onConfigureClick={handleConfigureClick}
      configData={configData}
    />
  );
});

export default GenerateComponent;
