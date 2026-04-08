import { act, renderHook } from "@testing-library/react";
import type { ProviderAccount } from "../../types";
import { useProviderFilter } from "../use-provider-filter";

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
    it("initializes with first provider selected", () => {
      const providers = [
        makeProvider({ id: "p1" }),
        makeProvider({ id: "p2" }),
      ];
      const { result } = renderHook(() => useProviderFilter(providers));
      expect(result.current.selectedProviderId).toBe("p1");
    });

    it("initializes with empty string when no providers given", () => {
      const { result } = renderHook(() => useProviderFilter([]));
      expect(result.current.selectedProviderId).toBe("");
    });

    it("returns only the first provider ID in providerIdsToQuery", () => {
      const providers = [
        makeProvider({ id: "p1" }),
        makeProvider({ id: "p2" }),
      ];
      const { result } = renderHook(() => useProviderFilter(providers));
      expect(result.current.providerIdsToQuery).toEqual(["p1"]);
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
        result.current.setSelectedProviderId("p2");
      });

      expect(result.current.providerIdsToQuery).toEqual(["p2"]);
      expect(result.current.selectedProviderId).toBe("p2");
    });

    it("providerIdsToQuery is always a single-element array", () => {
      const providers = [
        makeProvider({ id: "p1" }),
        makeProvider({ id: "p2" }),
        makeProvider({ id: "p3" }),
      ];
      const { result } = renderHook(() => useProviderFilter(providers));

      // Initially selects first provider — single element
      expect(result.current.providerIdsToQuery).toHaveLength(1);

      act(() => {
        result.current.setSelectedProviderId("p3");
      });

      expect(result.current.providerIdsToQuery).toHaveLength(1);
      expect(result.current.providerIdsToQuery).toEqual(["p3"]);
    });
  });

  describe("selects first provider once providers load", () => {
    it("updates selection when providers arrive after mount", () => {
      const { result, rerender } = renderHook(
        ({ list }: { list: ProviderAccount[] }) => useProviderFilter(list),
        { initialProps: { list: [] } },
      );

      expect(result.current.selectedProviderId).toBe("");

      rerender({
        list: [makeProvider({ id: "p1" }), makeProvider({ id: "p2" })],
      });

      expect(result.current.selectedProviderId).toBe("p1");
    });
  });

  describe("reset on provider deletion", () => {
    it("selects next available provider when selected provider is removed", () => {
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

      expect(result.current.selectedProviderId).toBe("p1");
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
