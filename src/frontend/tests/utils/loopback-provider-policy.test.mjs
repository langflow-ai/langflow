import assert from "node:assert/strict";
import { test } from "node:test";
import {
  applyLoopbackToExamples,
  applyLoopbackToFlowData,
  isFlowDataLoopbackConfigured,
  isLoopbackTarget,
  isNodeLoopbackConfigured,
  LOOPBACK_MODEL,
  LOOPBACK_OPENAI_API_KEY,
  LOOPBACK_OPENAI_BASE_URL,
  withLoopbackTemplate,
} from "./loopback-provider-policy.mjs";

function unifiedModelNode(overrides = {}) {
  return {
    id: "LanguageModel-abc",
    type: "genericNode",
    data: {
      type: "LanguageModelComponent",
      node: {
        template: {
          model: {
            _input_type: "ModelInput",
            type: "model",
            value: [{ name: "claude-sonnet-4", provider: "Anthropic" }],
            options: [{ name: "claude-sonnet-4", provider: "Anthropic" }],
          },
          api_key: { value: "", load_from_db: true },
          ...overrides,
        },
      },
    },
  };
}

function plainNode() {
  return {
    id: "ChatInput-xyz",
    type: "genericNode",
    data: {
      type: "ChatInput",
      node: { template: { input_value: { value: "hello" } } },
    },
  };
}

test("targets unified model inputs and OpenAI components only", () => {
  assert.equal(isLoopbackTarget(unifiedModelNode()), true);
  assert.equal(isLoopbackTarget(plainNode()), false);
  assert.equal(
    isLoopbackTarget({
      id: "OpenAI-1",
      data: { type: "OpenAIModel", node: { template: { api_key: {} } } },
    }),
    true,
  );
  assert.equal(isLoopbackTarget({ id: "no-template" }), false);
});

test("applies the loopback model, key and base url", () => {
  const node = withLoopbackTemplate(
    unifiedModelNode({ base_url: { value: "https://api.openai.com/v1" } }),
  );
  const template = node.data.node.template;

  assert.deepEqual(template.model.value, [LOOPBACK_MODEL]);
  assert.equal(template.api_key.value, LOOPBACK_OPENAI_API_KEY);
  assert.equal(template.api_key.load_from_db, false);
  assert.equal(template.base_url.value, LOOPBACK_OPENAI_BASE_URL);
});

test("prepends the loopback model without duplicating it", () => {
  const once = withLoopbackTemplate(unifiedModelNode());
  const twice = withLoopbackTemplate(once);
  const options = twice.data.node.template.model.options;

  assert.equal(options[0].name, LOOPBACK_MODEL.name);
  assert.equal(
    options.filter((option) => option.name === LOOPBACK_MODEL.name).length,
    1,
  );
});

test("never mutates its argument", () => {
  const node = unifiedModelNode();
  const snapshot = JSON.stringify(node);
  withLoopbackTemplate(node);
  assert.equal(JSON.stringify(node), snapshot);
});

test("leaves non-target nodes identical", () => {
  const node = plainNode();
  assert.equal(withLoopbackTemplate(node), node);
});

test("sets legacy model_name and provider fields", () => {
  const node = withLoopbackTemplate(
    unifiedModelNode({
      model_name: { value: "gpt-4" },
      provider: { value: "Anthropic" },
    }),
  );

  assert.equal(node.data.node.template.model_name.value, LOOPBACK_MODEL.name);
  assert.equal(node.data.node.template.provider.value, LOOPBACK_MODEL.provider);
});

test("does not overwrite a model_name that is itself a ModelInput", () => {
  const node = withLoopbackTemplate(
    unifiedModelNode({
      model_name: { _input_type: "ModelInput", value: "keep-me" },
    }),
  );

  assert.equal(node.data.node.template.model_name.value, "keep-me");
});

test("round-trips through the configured predicate", () => {
  const node = unifiedModelNode({ base_url: { value: "https://x/v1" } });
  assert.equal(isNodeLoopbackConfigured(node), false);
  assert.equal(isNodeLoopbackConfigured(withLoopbackTemplate(node)), true);
});

test("rejects a node whose api key was left bound to the variable store", () => {
  const node = withLoopbackTemplate(unifiedModelNode());
  node.data.node.template.api_key.load_from_db = true;
  assert.equal(isNodeLoopbackConfigured(node), false);
});

test("reports the target node ids for a flow", () => {
  const { data, targetNodeIds } = applyLoopbackToFlowData({
    nodes: [unifiedModelNode(), plainNode()],
    edges: [],
  });

  assert.deepEqual(targetNodeIds, ["LanguageModel-abc"]);
  assert.deepEqual(data.edges, []);
  assert.equal(isFlowDataLoopbackConfigured(data), true);
});

test("a flow with no model node is never considered configured", () => {
  assert.equal(isFlowDataLoopbackConfigured({ nodes: [plainNode()] }), false);
  assert.equal(isFlowDataLoopbackConfigured({ nodes: [] }), false);
});

test("seeds every example in the starter catalog", () => {
  const examples = [
    { id: "1", name: "Basic Prompting", data: { nodes: [unifiedModelNode()] } },
    { id: "2", name: "No Model", data: { nodes: [plainNode()] } },
    { id: "3", name: "Malformed" },
  ];
  const seeded = applyLoopbackToExamples(examples);

  assert.equal(isFlowDataLoopbackConfigured(seeded[0].data), true);
  assert.equal(seeded[0].name, "Basic Prompting");
  assert.deepEqual(seeded[1].data.nodes, [plainNode()]);
  assert.equal(seeded[2], examples[2]);
  assert.equal(isFlowDataLoopbackConfigured(examples[0].data), false);
});
