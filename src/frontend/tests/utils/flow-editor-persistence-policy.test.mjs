import assert from "node:assert/strict";
import test from "node:test";
import {
  canAcceptFullFlowAutosavePayload,
  isMatchingFullFlowAutosavePayload,
  isModelRefreshBody,
  modelRefreshNodeCount,
  requiresPostRefreshAutosave,
} from "./flow-editor-persistence-policy.mjs";

const configuredData = {
  nodes: [
    {
      id: "Agent-test",
      type: "genericNode",
      data: {
        node: {
          template: {
            model: { type: "model", value: [{ name: "gpt-4o-mini" }] },
          },
        },
      },
    },
  ],
};

const matchesConfiguredAgent = (data) =>
  data.nodes?.[0]?.data?.node?.template?.model?.value?.[0]?.name ===
  "gpt-4o-mini";

test("only an exact full-flow autosave satisfies the persistence barrier", () => {
  assert.equal(modelRefreshNodeCount(configuredData), 1);
  assert.equal(
    isMatchingFullFlowAutosavePayload(
      { data: configuredData },
      matchesConfiguredAgent,
    ),
    false,
    "the helper's data-only PATCH must not satisfy the barrier",
  );

  assert.equal(
    isMatchingFullFlowAutosavePayload(
      {
        data: configuredData,
        description: null,
        endpoint_name: null,
        folder_id: "project-test",
        locked: false,
        name: "Test flow",
      },
      matchesConfiguredAgent,
    ),
    true,
  );
  assert.equal(
    isMatchingFullFlowAutosavePayload(
      {
        data: { nodes: [] },
        description: null,
        endpoint_name: null,
        folder_id: "project-test",
        locked: false,
        name: "Stale flow",
      },
      matchesConfiguredAgent,
    ),
    false,
    "a full-flow PATCH with stale node data must not satisfy the barrier",
  );
});

test("zero-model flows do not require a post-refresh autosave", () => {
  const dataWithoutModelFields = {
    nodes: [
      {
        type: "genericNode",
        data: { node: { template: { query: { type: "str" } } } },
      },
    ],
  };

  assert.equal(modelRefreshNodeCount(dataWithoutModelFields), 0);
  assert.equal(requiresPostRefreshAutosave(dataWithoutModelFields), false);
});

test("recognizes refreshes for dynamically named model fields", () => {
  assert.equal(
    isModelRefreshBody({
      field: "embedding_model",
      template: {
        embedding_model: { type: "model", value: [] },
      },
    }),
    true,
  );
  assert.equal(
    isModelRefreshBody({
      field: "embedding_model",
      template: {
        embedding_model: { type: "str", value: "not a model" },
      },
    }),
    false,
  );
});

test("ignores a matching autosave until every refresh body finishes", () => {
  const fullFlowAutosave = {
    data: configuredData,
    description: null,
    endpoint_name: null,
    folder_id: "project-test",
    locked: false,
    name: "Test flow",
  };

  assert.equal(
    canAcceptFullFlowAutosavePayload(
      fullFlowAutosave,
      matchesConfiguredAgent,
      0,
      1,
    ),
    false,
    "a matching autosave arriving before refresh completion must be ignored",
  );
  assert.equal(
    canAcceptFullFlowAutosavePayload(
      fullFlowAutosave,
      matchesConfiguredAgent,
      1,
      1,
    ),
    true,
  );
});
