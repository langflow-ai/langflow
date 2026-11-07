import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { api } from "@/controllers/API/api";
import type { PolicyBundleRead, PolicyBundleWrite } from "../types";
import {
  getPolicyBundle,
  policyBundleKeys,
  replacePolicyBundle,
  usePolicyBundleQuery,
  useSavePolicyBundleMutation,
} from "../use-policy-bundle";

jest.mock("@/controllers/API/api", () => ({
  api: { get: jest.fn(), put: jest.fn() },
}));

describe("versioned policy bundle requests", () => {
  beforeEach(() => jest.clearAllMocks());

  it("reads the tri-state contract from API v2", async () => {
    const bundle = { approved_integration_provider_ids: null };
    jest.mocked(api.get).mockResolvedValue({ data: bundle });

    expect(await getPolicyBundle()).toBe(bundle);
    expect(api.get).toHaveBeenCalledWith("/api/v2/policy-bundle");
  });

  it.each([null, []])(
    "writes the integration ceiling %p through API v2",
    async (integrationProviders) => {
      const payload: PolicyBundleWrite = {
        expected_revision: 7,
        approved_provider_ids: ["openai"],
        blocked_component_keys: [],
        blocked_template_keys: [],
        blocked_model_keys: [],
        approved_integration_provider_ids: integrationProviders,
        blocked_integration_action_keys: [],
      };
      const saved = { ...payload, revision: 8 };
      jest.mocked(api.put).mockResolvedValue({ data: saved });

      expect(await replacePolicyBundle(payload)).toBe(saved);
      expect(api.put).toHaveBeenCalledWith("/api/v2/policy-bundle", payload);
    },
  );

  it("does not fall back to the ambiguous v1 contract when an old replica rejects v2", async () => {
    const failure = { response: { status: 404 } };
    jest.mocked(api.put).mockRejectedValue(failure);
    const payload: PolicyBundleWrite = {
      expected_revision: 7,
      approved_provider_ids: [],
      blocked_component_keys: [],
      blocked_template_keys: [],
      blocked_model_keys: [],
      approved_integration_provider_ids: [],
      blocked_integration_action_keys: [],
    };

    await expect(replacePolicyBundle(payload)).rejects.toBe(failure);
    expect(api.put).toHaveBeenCalledTimes(1);
    expect(api.put).toHaveBeenCalledWith("/api/v2/policy-bundle", payload);
  });

  it("loads the versioned bundle through the policy query", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    });
    const bundle = { approved_integration_provider_ids: [] };
    jest.mocked(api.get).mockResolvedValue({ data: bundle });
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children);

    const { result } = renderHook(() => usePolicyBundleQuery(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBe(bundle);
    expect(api.get).toHaveBeenCalledWith("/api/v2/policy-bundle");
    client.clear();
  });

  it("preserves deny-all while saving an unrelated edit and updates the bundle cache", async () => {
    const client = new QueryClient({
      defaultOptions: { mutations: { retry: false, gcTime: Infinity } },
    });
    const bundle: PolicyBundleRead = {
      revision: 7,
      initialized: true,
      source: "api",
      approved_provider_ids: [],
      blocked_component_keys: [],
      blocked_template_keys: [],
      blocked_model_keys: [],
      approved_integration_provider_ids: [],
      blocked_integration_action_keys: [],
      content_hash: "hash",
      created_at: "2026-11-06T00:00:00Z",
      created_by: null,
      reason: null,
      rollback_of_revision: null,
      managed_externally: false,
    };
    const saved = {
      ...bundle,
      revision: 8,
      blocked_component_keys: ["ChatInput"],
    };
    jest.mocked(api.put).mockResolvedValue({ data: saved });
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children);
    const { result } = renderHook(() => useSavePolicyBundleMutation(), {
      wrapper,
    });

    await act(async () => {
      await result.current.mutateAsync({
        bundle,
        changes: { blocked_component_keys: ["ChatInput"] },
      });
    });

    expect(api.put).toHaveBeenCalledWith(
      "/api/v2/policy-bundle",
      expect.objectContaining({
        expected_revision: 7,
        approved_integration_provider_ids: [],
        blocked_component_keys: ["ChatInput"],
      }),
    );
    expect(client.getQueryData(policyBundleKeys.current())).toEqual(saved);
    expect(
      client.getQueryState(policyBundleKeys.current())?.isInvalidated,
    ).toBe(true);
    client.clear();
  });
});
