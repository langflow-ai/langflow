import { useMemo } from "react";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import { isModelEnabledForType } from "@/controllers/API/helpers/enabled-model-policy";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";

/** Language models the user may run in this flow's scope, for the LLM judge picker. */
export function useJudgeModelOptions(flowId: string, enabled: boolean) {
  const providersQuery = useGetModelProviders(
    { flowId, purpose: "use" },
    { enabled: enabled && Boolean(flowId) },
  );
  const enabledModelsQuery = useGetEnabledModels({
    flowId,
    enabled: enabled && Boolean(flowId),
    purpose: "use",
  });
  const ready = providersQuery.isSuccess && enabledModelsQuery.isSuccess;

  const options = useMemo<ModelOption[]>(() => {
    const enabledModels = enabledModelsQuery.data;
    if (!ready || !enabledModels) return [];
    return (providersQuery.data ?? [])
      .filter((provider) => provider.is_enabled)
      .flatMap((provider) =>
        provider.models
          .filter(
            (model) =>
              model.metadata?.model_type === "llm" &&
              isModelEnabledForType(
                enabledModels,
                provider.provider,
                model.model_name,
                "llm",
              ),
          )
          .map((model) => ({
            id: model.model_name,
            name: model.model_name,
            icon: provider.icon || "Bot",
            provider: provider.provider,
            metadata: model.metadata,
          })),
      );
  }, [ready, enabledModelsQuery.data, providersQuery.data]);

  return { options, ready };
}
