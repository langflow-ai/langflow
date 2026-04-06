import { act, renderHook } from "@testing-library/react";
import type { ProviderAccount } from "../../types";
import { ALL_PROVIDERS, useProviderFilter } from "../use-provider-filter";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeProvider = (
  overrides: Partial<ProviderAccount> = {},
): ProviderAccount => ({
  id: "p1",
  name: "Prod Environment",
  provider_tenant_id: "tenant-1",
  provider_key: "watsonx-orchestrate",
  provider_url: "https://api.example.com",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
  ...overrides,
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useProviderFilter", () => {
  describe("initial state", () => {
    it("initializes with ALL_PROVIDERS selected", () => {
      const { result } = renderHook(() => useProviderFilter([]));
      expect(result.current.selectedProviderId).toBe(ALL_PROVIDERS);
    });

    it("returns all provider IDs in providerIdsToQuery when all selected", () => {
      const providers = [
        makeProvider({ id: "p1" }),
        makeProvider({ id: "p2" }),
      ];
      const { result } = renderHook(() => useProviderFilter(providers));
      expect(result.current.providerIdsToQuery).toEqual(["p1", "p2"]);
    });

    it("returns empty providerIdsToQuery for empty provider list", () => {
      const { result } = renderHook(() => useProviderFilter([]));
      expect(result.current.providerIdsToQuery).toEqual([]);
    });

    it("builds providerMap from provider list", () => {
      const providers = [
        makeProvider({ id: "p1", name: "Prod" }),
        makeProvider({ id: "p2", name: "Staging" }),
      ];
      const { result } = renderHook(() => useProviderFilter(providers));
      expect(result.current.providerMap).toEqual({ p1: "Prod", p2: "Staging" });
    });

    it("returns empty providerMap for empty provider list", () => {
      const { result } = renderHook(() => useProviderFilter([]));
      expect(result.current.providerMap).toEqual({});
    });
  });

  describe("provider selection", () => {
    it("returns only the selected provider ID in providerIdsToQuery", () => {
      const providers = [
        makeProvider({ id: "p1" }),
        makeProvider({ id: "p2" }),
      ];
      const { result } = renderHook(() => useProviderFilter(providers));

      act(() => {
        result.current.setSelectedProviderId("p1");
      });

      expect(result.current.providerIdsToQuery).toEqual(["p1"]);
      expect(result.current.selectedProviderId).toBe("p1");
    });

    it("returns all IDs after resetting back to ALL_PROVIDERS", () => {
      const providers = [
        makeProvider({ id: "p1" }),
        makeProvider({ id: "p2" }),
      ];
      const { result } = renderHook(() => useProviderFilter(providers));

      act(() => {
        result.current.setSelectedProviderId("p1");
      });
      act(() => {
        result.current.setSelectedProviderId(ALL_PROVIDERS);
      });

      expect(result.current.providerIdsToQuery).toEqual(["p1", "p2"]);
    });
  });

  describe("reset on provider deletion", () => {
    it("resets to ALL_PROVIDERS when the selected provider is removed from the list", () => {
      const providers = [
        makeProvider({ id: "p1" }),
        makeProvider({ id: "p2" }),
      ];
      const { result, rerender } = renderHook(
        ({ list }: { list: ProviderAccount[] }) => useProviderFilter(list),
        { initialProps: { list: providers } },
      );

      act(() => {
        result.current.setSelectedProviderId("p2");
      });
      expect(result.current.selectedProviderId).toBe("p2");

      rerender({ list: [makeProvider({ id: "p1" })] });

      expect(result.current.selectedProviderId).toBe(ALL_PROVIDERS);
    });

    it("does not reset when the selected provider still exists", () => {
      const providers = [
        makeProvider({ id: "p1" }),
        makeProvider({ id: "p2" }),
      ];
      const { result, rerender } = renderHook(
        ({ list }: { list: ProviderAccount[] }) => useProviderFilter(list),
        { initialProps: { list: providers } },
      );

      act(() => {
        result.current.setSelectedProviderId("p1");
      });

      // Remove p2 (not the selected one)
      rerender({ list: [makeProvider({ id: "p1" })] });

      expect(result.current.selectedProviderId).toBe("p1");
    });

    it("does not reset when ALL_PROVIDERS is selected and a provider is removed", () => {
      const providers = [
        makeProvider({ id: "p1" }),
        makeProvider({ id: "p2" }),
      ];
      const { result, rerender } = renderHook(
        ({ list }: { list: ProviderAccount[] }) => useProviderFilter(list),
        { initialProps: { list: providers } },
      );

      expect(result.current.selectedProviderId).toBe(ALL_PROVIDERS);

      rerender({ list: [makeProvider({ id: "p1" })] });

      expect(result.current.selectedProviderId).toBe(ALL_PROVIDERS);
    });

    it("does not reset when the provider list is empty and ALL_PROVIDERS is selected", () => {
      const { result, rerender } = renderHook(
        ({ list }: { list: ProviderAccount[] }) => useProviderFilter(list),
        { initialProps: { list: [makeProvider({ id: "p1" })] } },
      );

      // Don't select a specific provider — stay at ALL_PROVIDERS
      rerender({ list: [] });

      expect(result.current.selectedProviderId).toBe(ALL_PROVIDERS);
    });
  });

  describe("providerMap updates", () => {
    it("updates providerMap when providers list changes", () => {
      const initial = [makeProvider({ id: "p1", name: "Prod" })];
      const { result, rerender } = renderHook(
        ({ list }: { list: ProviderAccount[] }) => useProviderFilter(list),
        { initialProps: { list: initial } },
      );

      expect(result.current.providerMap).toEqual({ p1: "Prod" });

      rerender({
        list: [
          makeProvider({ id: "p1", name: "Prod" }),
          makeProvider({ id: "p2", name: "Staging" }),
        ],
      });

      expect(result.current.providerMap).toEqual({ p1: "Prod", p2: "Staging" });
    });
  });
});
