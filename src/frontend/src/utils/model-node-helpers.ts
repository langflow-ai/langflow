import type {
  APIClassType,
  APITemplateType,
  ModelOptionType,
} from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import { isUserOwnedModelKind, modelKindOfField } from "./model-kind";

/** Checks if a node has a model-type input field */
export function isModelNode(node: AllNodeType): boolean {
  if (node.type !== "genericNode") return false;
  const template = node.data?.node?.template;
  if (!template) return false;

  // biome-ignore lint/suspicious/noExplicitAny: legacy
  return Object.values(template).some((field: any) => field?.type === "model");
}

/**
 * The model fields a refresh must cover: every shown one. Smart Router has a
 * language and a decision model field and shows one per mode. A node whose
 * model fields are all hidden falls back to its first, as before.
 */
export function findModelFieldKeys(template: APITemplateType): string[] {
  const keys = Object.keys(template).filter(
    (key) => template[key]?.type === "model",
  );
  const shown = keys.filter((key) => template[key]?.show !== false);
  return shown.length > 0 ? shown : keys.slice(0, 1);
}

/** Builds the refresh API payload with flow context */
export function buildRefreshPayload(
  template: APITemplateType,
  flowId: string | undefined,
  folderId: string | undefined,
  // biome-ignore lint/suspicious/noExplicitAny: legacy
): Record<string, any> {
  return {
    ...template,
    ...(flowId && { _frontend_node_flow_id: { value: flowId } }),
    ...(folderId && { _frontend_node_folder_id: { value: folderId } }),
    is_refresh: true,
  };
}

/** Creates an updated node with new template data */
export function createUpdatedNode(
  currentNode: AllNodeType,
  updatedTemplate: APITemplateType,
  updatedOutputs?: APIClassType["outputs"],
): AllNodeType {
  return {
    ...currentNode,
    data: {
      ...currentNode.data,
      node: {
        ...currentNode.data.node,
        template: updatedTemplate,
        outputs: updatedOutputs ?? currentNode.data.node.outputs,
      },
    },
  };
}

/** Validates and corrects model value against available options */
export function validateModelValue(
  template: APITemplateType,
  modelFieldKey: string,
  providerConfiguration?: ReadonlyMap<string, boolean>,
): APITemplateType {
  const modelField = template[modelFieldKey];
  if (!modelField) return template;
  // Only language and embedding fields are corrected on load. A missing or
  // unavailable decision model stays as saved and fails clearly when the flow
  // runs, and a field of unknown kind is left for the picker to refuse.
  const kind = modelKindOfField(modelField);
  if (kind === null || isUserOwnedModelKind(kind)) return template;

  const options = modelField.options || [];
  const currentValue = modelField.value;

  // Filter out disabled provider placeholders to get actual available models
  const availableOptions = options.filter(
    (opt: ModelOptionType) => !opt?.metadata?.is_disabled_provider,
  );

  const currentModel = Array.isArray(currentValue)
    ? currentValue[0]
    : currentValue;
  const currentModelName = currentModel?.name;
  const currentProvider = currentModel?.provider;
  const currentProviderConfiguration = currentProvider
    ? providerConfiguration?.get(currentProvider)
    : undefined;

  // Sticky defaults can be disconnected providers or configured providers
  // whose valid model is not locally enabled. Reject only an explicitly
  // disconnected provider, and only when another selectable model exists.
  const selectableOptions = availableOptions.filter(
    (opt: ModelOptionType) =>
      opt?.metadata?.not_enabled_locally !== true &&
      (!opt.provider || providerConfiguration?.get(opt.provider) !== false),
  );
  const optionsForValidation =
    currentProviderConfiguration === false && selectableOptions.length > 0
      ? selectableOptions
      : availableOptions;

  // Check if current model is still available
  const isCurrentModelValid =
    currentModelName &&
    optionsForValidation.some(
      (opt: ModelOptionType) =>
        opt.name === currentModelName &&
        (!currentProvider || opt.provider === currentProvider),
    );

  if (isCurrentModelValid) {
    // Current value is valid, no changes needed
    return template;
  }

  // Current value is invalid - need to update it
  if (optionsForValidation.length > 0) {
    // Select the first available model
    const firstOption = optionsForValidation[0];
    const newValue = [
      {
        ...(firstOption.id && { id: firstOption.id }),
        name: firstOption.name,
        icon: firstOption.icon || "Bot",
        provider: firstOption.provider || "Unknown",
        metadata: firstOption.metadata ?? {},
      },
    ];
    return {
      ...template,
      [modelFieldKey]: {
        ...modelField,
        value: newValue,
      },
    };
  }

  // No available options - clear the value
  return {
    ...template,
    [modelFieldKey]: {
      ...modelField,
      value: [],
    },
  };
}
