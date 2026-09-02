import assert from "node:assert/strict";
import test from "node:test";
import {
  isModelRefreshBarrierSatisfied,
  isModelRefreshBody,
  modelRefreshFlowId,
  modelRefreshNodeCount,
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

test("counts the model refreshes required after a reload", () => {
  assert.equal(modelRefreshNodeCount(configuredData), 1);
});

test("zero-model flows do not require a refresh barrier", () => {
  const dataWithoutModelFields = {
    nodes: [
      {
        type: "genericNode",
        data: { node: { template: { query: { type: "str" } } } },
      },
    ],
  };

  assert.equal(modelRefreshNodeCount(dataWithoutModelFields), 0);
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

test("attributes a refresh to the flow stamped on its template", () => {
  assert.equal(
    modelRefreshFlowId({
      field: "model",
      template: {
        model: { type: "model", value: [] },
        _frontend_node_flow_id: { value: "flow-1" },
      },
    }),
    "flow-1",
  );
});

test("has no flow for an unstamped or non-refresh body", () => {
  assert.equal(
    modelRefreshFlowId({
      field: "model",
      template: { model: { type: "model", value: [] } },
    }),
    undefined,
  );
  assert.equal(
    modelRefreshFlowId({
      field: "model",
      template: {
        model: { type: "model", value: [] },
        _frontend_node_flow_id: { value: "" },
      },
    }),
    undefined,
  );
  assert.equal(
    modelRefreshFlowId({
      field: "code",
      template: {
        code: { type: "code" },
        _frontend_node_flow_id: { value: "flow-1" },
      },
    }),
    undefined,
  );
});

test("the refresh barrier waits for every expected response", () => {
  assert.equal(
    isModelRefreshBarrierSatisfied(0, 1),
    false,
    "the first refresh still has to finish",
  );
  assert.equal(
    isModelRefreshBarrierSatisfied(1, 2),
    false,
    "a second expected refresh must finish before the listener is disposed",
  );
  assert.equal(isModelRefreshBarrierSatisfied(2, 2), true);
});
