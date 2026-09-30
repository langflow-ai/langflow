export const LOOPBACK_OPENAI_BASE_URL = "http://127.0.0.1:8787/v1";
export const LOOPBACK_OPENAI_API_KEY = "langflow-loopback-test-key"; // pragma: allowlist secret

export const LOOPBACK_MODEL = {
  id: "gpt-4o-mini",
  name: "gpt-4o-mini",
  icon: "OpenAI",
  provider: "OpenAI",
  category: "OpenAI",
  metadata: {
    api_key_param: "api_key", // pragma: allowlist secret
    context_length: 128_000,
    max_tokens_field_name: "max_tokens",
    model_class: "ChatOpenAI",
    model_name_param: "model",
  },
};

const API_KEY_FIELDS = ["api_key", "openai_api_key"];
const BASE_URL_FIELDS = ["openai_api_base", "base_url"];

function isRecord(value) {
  return typeof value === "object" && value !== null;
}

function template(node) {
  const candidate = node?.data?.node?.template;
  return isRecord(candidate) ? candidate : undefined;
}

function hasUnifiedModelInput(nodeTemplate) {
  return nodeTemplate.model?._input_type === "ModelInput";
}

/**
 * A node is a loopback target when it exposes the unified model input or is an
 * OpenAI-family component. Everything else is left untouched.
 */
export function isLoopbackTarget(node) {
  const nodeTemplate = template(node);
  if (!nodeTemplate) return false;
  return (
    hasUnifiedModelInput(nodeTemplate) || /openai/i.test(node?.data?.type ?? "")
  );
}

function loopbackModelOptions(existingOptions) {
  return [
    LOOPBACK_MODEL,
    ...(existingOptions ?? []).filter(
      (option) =>
        !(
          isRecord(option) &&
          option.name === LOOPBACK_MODEL.name &&
          option.provider === LOOPBACK_MODEL.provider
        ),
    ),
  ];
}

function withLoopbackFields(nodeTemplate) {
  const next = { ...nodeTemplate };

  if (hasUnifiedModelInput(nodeTemplate)) {
    next.model = {
      ...nodeTemplate.model,
      value: [LOOPBACK_MODEL],
      options: loopbackModelOptions(nodeTemplate.model.options),
    };
  }

  for (const field of API_KEY_FIELDS) {
    if (nodeTemplate[field]) {
      next[field] = {
        ...nodeTemplate[field],
        value: LOOPBACK_OPENAI_API_KEY,
        load_from_db: false,
      };
    }
  }
  for (const field of BASE_URL_FIELDS) {
    if (nodeTemplate[field]) {
      next[field] = {
        ...nodeTemplate[field],
        value: LOOPBACK_OPENAI_BASE_URL,
      };
    }
  }
  if (
    nodeTemplate.model_name &&
    nodeTemplate.model_name._input_type !== "ModelInput"
  ) {
    next.model_name = {
      ...nodeTemplate.model_name,
      value: LOOPBACK_MODEL.name,
    };
  }
  if (nodeTemplate.provider) {
    next.provider = {
      ...nodeTemplate.provider,
      value: LOOPBACK_MODEL.provider,
    };
  }

  return next;
}

/**
 * Returns a new node with the loopback provider applied, or the original node
 * when it is not a loopback target. Never mutates its argument.
 */
export function withLoopbackTemplate(node) {
  if (!isLoopbackTarget(node)) return node;
  const nodeTemplate = template(node);
  return {
    ...node,
    data: {
      ...node.data,
      node: {
        ...node.data.node,
        template: withLoopbackFields(nodeTemplate),
      },
    },
  };
}

export function isNodeLoopbackConfigured(node) {
  const nodeTemplate = template(node);
  if (!nodeTemplate) return false;
  if (!isLoopbackTarget(node)) return false;

  if (hasUnifiedModelInput(nodeTemplate)) {
    const value = nodeTemplate.model.value;
    if (
      !Array.isArray(value) ||
      !value.some(
        (model) =>
          isRecord(model) &&
          model.name === LOOPBACK_MODEL.name &&
          model.provider === LOOPBACK_MODEL.provider,
      )
    ) {
      return false;
    }
  }

  for (const field of API_KEY_FIELDS) {
    if (
      nodeTemplate[field] &&
      (nodeTemplate[field].value !== LOOPBACK_OPENAI_API_KEY ||
        nodeTemplate[field].load_from_db !== false)
    ) {
      return false;
    }
  }
  for (const field of BASE_URL_FIELDS) {
    if (
      nodeTemplate[field] &&
      nodeTemplate[field].value !== LOOPBACK_OPENAI_BASE_URL
    ) {
      return false;
    }
  }
  if (
    nodeTemplate.model_name &&
    nodeTemplate.model_name._input_type !== "ModelInput" &&
    nodeTemplate.model_name.value !== LOOPBACK_MODEL.name
  ) {
    return false;
  }
  if (
    nodeTemplate.provider &&
    nodeTemplate.provider.value !== LOOPBACK_MODEL.provider
  ) {
    return false;
  }
  return true;
}

/**
 * Applies the loopback provider to every target node in a flow's `data`,
 * returning the new data plus the ids of the nodes it targeted. `targetNodeIds`
 * is what callers assert on later — a flow with none of them cannot be driven
 * against the loopback provider at all.
 */
export function applyLoopbackToFlowData(data) {
  const nodes = data?.nodes ?? [];
  const targetNodeIds = nodes
    .filter(isLoopbackTarget)
    .map((node) => node.id)
    .filter((id) => typeof id === "string" && id.length > 0);

  return {
    data: { ...data, nodes: nodes.map(withLoopbackTemplate) },
    targetNodeIds,
  };
}

export function isFlowDataLoopbackConfigured(data) {
  const targets = (data?.nodes ?? []).filter(isLoopbackTarget);
  return targets.length > 0 && targets.every(isNodeLoopbackConfigured);
}

/**
 * Rewrites the starter-template catalog so templates are born configured for
 * the loopback provider. Templates without a model input pass through
 * untouched.
 */
export function applyLoopbackToExamples(examples) {
  return examples.map((example) => {
    if (!isRecord(example) || !isRecord(example.data)) return example;
    const { data } = applyLoopbackToFlowData(example.data);
    return { ...example, data };
  });
}
