import type { Page } from "@playwright/test";
import { expect } from "../fixtures";
import { adjustScreenView } from "./adjust-screen-view";
import { waitForFlowEditorReady } from "./flow/wait-for-flow-editor-ready";
import { updateOldComponents } from "./update-old-components";

export const LOOPBACK_OPENAI_BASE_URL = "http://127.0.0.1:8787/v1";
export const LOOPBACK_OPENAI_API_KEY = "langflow-loopback-test-key"; // pragma: allowlist secret

const LOOPBACK_MODEL = {
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

type TemplateField = {
  _input_type?: string;
  load_from_db?: boolean;
  options?: unknown[];
  value?: unknown;
};

type FlowNode = {
  id?: string;
  data?: {
    node?: {
      template?: Record<string, TemplateField>;
    };
    type?: string;
  };
};

type FlowRead = {
  data?: { nodes?: FlowNode[]; edges?: unknown[] };
};

function configureTemplate(node: FlowNode): boolean {
  const template = node.data?.node?.template;
  if (!template) return false;

  const modelInput = template.model;
  const hasUnifiedModel = modelInput?._input_type === "ModelInput";
  const isOpenAIComponent = /openai/i.test(node.data?.type ?? "");
  if (!hasUnifiedModel && !isOpenAIComponent) return false;

  if (hasUnifiedModel) {
    modelInput.value = [LOOPBACK_MODEL];
    modelInput.options = [
      LOOPBACK_MODEL,
      ...(modelInput.options ?? []).filter(
        (option) =>
          !(
            typeof option === "object" &&
            option !== null &&
            "name" in option &&
            option.name === LOOPBACK_MODEL.name &&
            "provider" in option &&
            option.provider === LOOPBACK_MODEL.provider
          ),
      ),
    ];
  }

  for (const fieldName of ["api_key", "openai_api_key"]) {
    if (template[fieldName]) {
      template[fieldName].value = LOOPBACK_OPENAI_API_KEY;
      template[fieldName].load_from_db = false;
    }
  }
  for (const fieldName of ["openai_api_base", "base_url"]) {
    if (template[fieldName]) {
      template[fieldName].value = LOOPBACK_OPENAI_BASE_URL;
    }
  }
  if (template.model_name && template.model_name._input_type !== "ModelInput") {
    template.model_name.value = LOOPBACK_MODEL.name;
  }
  if (template.provider) template.provider.value = LOOPBACK_MODEL.provider;
  return true;
}

function isLoopbackConfigured(node: FlowNode): boolean {
  const template = node.data?.node?.template;
  if (!template) return false;

  const modelInput = template.model;
  const hasUnifiedModel = modelInput?._input_type === "ModelInput";
  const isOpenAIComponent = /openai/i.test(node.data?.type ?? "");
  if (!hasUnifiedModel && !isOpenAIComponent) return false;

  if (hasUnifiedModel) {
    if (
      !Array.isArray(modelInput.value) ||
      !modelInput.value.some(
        (model) =>
          typeof model === "object" &&
          model !== null &&
          "name" in model &&
          model.name === LOOPBACK_MODEL.name &&
          "provider" in model &&
          model.provider === LOOPBACK_MODEL.provider,
      )
    ) {
      return false;
    }
  }

  for (const fieldName of ["api_key", "openai_api_key"]) {
    if (
      template[fieldName] &&
      (template[fieldName].value !== LOOPBACK_OPENAI_API_KEY ||
        template[fieldName].load_from_db !== false)
    ) {
      return false;
    }
  }
  for (const fieldName of ["openai_api_base", "base_url"]) {
    if (
      template[fieldName] &&
      template[fieldName].value !== LOOPBACK_OPENAI_BASE_URL
    ) {
      return false;
    }
  }
  if (
    template.model_name &&
    template.model_name._input_type !== "ModelInput" &&
    template.model_name.value !== LOOPBACK_MODEL.name
  ) {
    return false;
  }
  if (
    template.provider &&
    template.provider.value !== LOOPBACK_MODEL.provider
  ) {
    return false;
  }
  return true;
}

function currentFlowId(page: Page): string {
  const match = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/);
  if (!match) throw new Error(`Expected a flow URL, received ${page.url()}`);
  return match[1];
}

export async function configureLoopbackOpenAI(
  page: Page,
  options?: {
    skipAdjustScreenView?: boolean;
    skipUpdateOldComponents?: boolean;
  },
): Promise<void> {
  if (!options?.skipAdjustScreenView) await adjustScreenView(page);
  if (!options?.skipUpdateOldComponents) await updateOldComponents(page);

  const flowId = currentFlowId(page);
  const flowResponse = await page.request.get(`/api/v1/flows/${flowId}`);
  expect(flowResponse.ok(), `GET flow ${flowId}`).toBeTruthy();
  const flow = (await flowResponse.json()) as FlowRead;
  const configuredNodes = (flow.data?.nodes ?? []).filter(configureTemplate);
  if (configuredNodes.length === 0) {
    throw new Error(`Flow ${flowId} has no OpenAI-compatible model inputs`);
  }

  const updateResponse = await page.request.patch(`/api/v1/flows/${flowId}`, {
    data: { data: flow.data },
  });
  expect(updateResponse.ok(), `PATCH flow ${flowId}`).toBeTruthy();

  const configuredNodeIds = configuredNodes.flatMap((node) =>
    node.id ? [node.id] : [],
  );
  if (configuredNodeIds.length !== configuredNodes.length) {
    throw new Error(`Flow ${flowId} contains a model node without an id`);
  }

  await page.reload();
  await waitForFlowEditorReady(page);
  const verifyResponse = await page.request.get(`/api/v1/flows/${flowId}`);
  expect(verifyResponse.ok(), `Verify flow ${flowId}`).toBeTruthy();
  const verifiedFlow = (await verifyResponse.json()) as FlowRead;
  const verifiedNodes = new Map(
    (verifiedFlow.data?.nodes ?? []).flatMap((node) =>
      node.id ? [[node.id, node]] : [],
    ),
  );
  const clobberedNodeIds = configuredNodeIds.filter((id) => {
    const node = verifiedNodes.get(id);
    return !node || !isLoopbackConfigured(node);
  });
  if (clobberedNodeIds.length > 0) {
    throw new Error(
      `Loopback model configuration was overwritten for nodes: ${clobberedNodeIds.join(", ")}`,
    );
  }
  if (!options?.skipAdjustScreenView) await adjustScreenView(page);
}
