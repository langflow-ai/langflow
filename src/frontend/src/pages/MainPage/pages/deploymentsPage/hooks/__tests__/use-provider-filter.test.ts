import { act, renderHook } from "@testing-library/react";
import type { ProviderAccount } from "../../types";
import { useProviderFilter } from "../use-provider-filter";

const makeProvider = (
  overrides: Partial<ProviderAccount> = {},
): ProviderAccount => ({
  id: "p1",
  name: "Prod Environment",
  provider_key: "watsonx-orchestrate",
  provider_data: {
    tenant_id: "tenant-1",
    url: "https://api.example.com",
  },
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
  ...overrides,
});

describe("useProviderFilter", () => {
  it("returns only the selected provider ID in providerIdsToQuery", () => {
    const providers = [makeProvider({ id: "p1" }), makeProvider({ id: "p2" })];
    const { result } = renderHook(() => useProviderFilter(providers));
    expect(result.current.providerIdsToQuery).toEqual(["p1"]);
    expect(result.current.selectedProviderId).toBe("p1");
  });

  it("returns empty providerIdsToQuery for empty provider list", () => {
    const { result } = renderHook(() => useProviderFilter([]));
    expect(result.current.providerIdsToQuery).toEqual([]);
    expect(result.current.selectedProviderId).toBe("");
  });

  it("builds providerMap from provider list", () => {
    const providers = [
      makeProvider({ id: "p1", name: "Prod" }),
      makeProvider({ id: "p2", name: "Staging" }),
    ];
    const { result } = renderHook(() => useProviderFilter(providers));
    expect(result.current.providerMap).toEqual({ p1: "Prod", p2: "Staging" });
  });

  it("allows changing selectedProviderId", () => {
    const providers = [
      makeProvider({ id: "p1", name: "Prod" }),
      makeProvider({ id: "p2", name: "Staging" }),
    ];
    const { result } = renderHook(() => useProviderFilter(providers));
    act(() => {
      result.current.setSelectedProviderId("p2");
    });
    expect(result.current.selectedProviderId).toBe("p2");
    expect(result.current.providerIdsToQuery).toEqual(["p2"]);
  });

  it("returns empty providerMap for empty provider list", () => {
    const { result } = renderHook(() => useProviderFilter([]));
    expect(result.current.providerMap).toEqual({});
  });

  it("updates providerIdsToQuery and providerMap when providers list changes", () => {
    const initial = [makeProvider({ id: "p1", name: "Prod" })];
    const { result, rerender } = renderHook(
      ({ list }: { list: ProviderAccount[] }) => useProviderFilter(list),
      { initialProps: { list: initial } },
    );

    expect(result.current.providerIdsToQuery).toEqual(["p1"]);
    expect(result.current.providerMap).toEqual({ p1: "Prod" });

    rerender({
      list: [
        makeProvider({ id: "p1", name: "Prod" }),
        makeProvider({ id: "p2", name: "Staging" }),
      ],
    });

    expect(result.current.providerIdsToQuery).toEqual(["p1"]);
    expect(result.current.providerMap).toEqual({ p1: "Prod", p2: "Staging" });
    expect(result.current.selectedProviderId).toBe("p1");
  });

  it("selects the first provider once providers load after starting empty", async () => {
    const { result, rerender } = renderHook(
      ({ list }: { list: ProviderAccount[] }) => useProviderFilter(list),
      { initialProps: { list: [] } },
    );

    expect(result.current.selectedProviderId).toBe("");

    await act(async () => {
      rerender({ list: [makeProvider({ id: "p1", name: "Prod" })] });
    });

    expect(result.current.selectedProviderId).toBe("p1");
  });

  it("providerIdsToQuery follows selectedProviderId", () => {
    const providers = [makeProvider({ id: "p1" }), makeProvider({ id: "p2" })];
    const { result } = renderHook(() => useProviderFilter(providers));

    expect(result.current.providerIdsToQuery).toEqual(["p1"]);

    act(() => {
      result.current.setSelectedProviderId("p2");
    });

    expect(result.current.providerIdsToQuery).toEqual(["p2"]);
  });

  it("resets selection to the first available provider when the selected provider is removed", async () => {
    const { result, rerender } = renderHook(
      ({ list }: { list: ProviderAccount[] }) => useProviderFilter(list),
      {
        initialProps: {
          list: [
            makeProvider({ id: "p1", name: "Prod" }),
            makeProvider({ id: "p2", name: "Staging" }),
          ],
        },
      },
    );

    act(() => {
      result.current.setSelectedProviderId("p2");
    });
    expect(result.current.selectedProviderId).toBe("p2");

    await act(async () => {
      rerender({ list: [makeProvider({ id: "p1", name: "Prod" })] });
    });

    expect(result.current.selectedProviderId).toBe("p1");
  });
});
