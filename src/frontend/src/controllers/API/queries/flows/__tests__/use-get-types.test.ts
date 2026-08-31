import { renderHook, waitFor } from "@testing-library/react";
import { useEffect, useState } from "react";

const mockApiGet = jest.fn();
const mockActivateScope = jest.fn();
const mockClearScopedTypes = jest.fn(() => true);
const mockSetScopedTypes = jest.fn(() => true);
const mockRecomputeComponentsToUpdateIfNeeded = jest.fn();
const mockQuery = jest.fn((key, fn, _options) => {
  const [data, setData] = useState<unknown>();
  const keyString = JSON.stringify(key);
  useEffect(() => {
    void fn().then(setData);
  }, [keyString]);
  return {
    data,
    dataUpdatedAt: data === undefined ? 0 : 1,
    fetchStatus: data === undefined ? "fetching" : "idle",
    isFetching: data === undefined,
    isLoading: data === undefined,
    isSuccess: data !== undefined,
    error: null,
  };
});

const mockUseTypesStore = Object.assign(
  jest.fn(
    (
      selector: (state: {
        activateScope: typeof mockActivateScope;
        clearScopedTypes: typeof mockClearScopedTypes;
        setScopedTypes: typeof mockSetScopedTypes;
      }) => unknown,
    ) =>
      selector({
        activateScope: mockActivateScope,
        clearScopedTypes: mockClearScopedTypes,
        setScopedTypes: mockSetScopedTypes,
      }),
  ),
  {
    getState: () => ({
      types: {},
    }),
  },
);

jest.mock("@/controllers/API/api", () => ({
  api: {
    get: mockApiGet,
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn((key) => `/api/v1/${key.toLowerCase()}`),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    query: mockQuery,
  })),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  recomputeComponentsToUpdateIfNeeded: mockRecomputeComponentsToUpdateIfNeeded,
  syncNodeTranslations: jest.fn(),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { setIsLoading: jest.Mock }) => unknown) =>
    selector({
      setIsLoading: jest.fn(),
    }),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: mockUseTypesStore,
}));

import { useGetTypes } from "../use-get-types";

describe("useGetTypes", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("recomputes componentsToUpdate after templates load", async () => {
    const responseData = {
      test_category: {
        TestComponent: {
          template: {},
        },
      },
    };
    mockApiGet.mockResolvedValue({ data: responseData });

    renderHook(() => useGetTypes());

    await waitFor(() =>
      expect(mockSetScopedTypes).toHaveBeenCalledWith(
        "global",
        responseData,
        {},
      ),
    );
    expect(mockRecomputeComponentsToUpdateIfNeeded).toHaveBeenCalled();
  });

  it("scopes the palette request and cache key by flow", async () => {
    mockApiGet.mockResolvedValue({ data: {} });

    renderHook(() => useGetTypes({ flowId: "flow-one" }));
    await waitFor(() => expect(mockApiGet).toHaveBeenCalled());

    expect(mockApiGet).toHaveBeenCalledWith(
      "/api/v1/all?force_refresh=true&flow_id=flow-one",
    );
    expect(mockQuery).toHaveBeenCalledWith(
      ["useGetTypes", "flow-one", undefined],
      expect.any(Function),
      {
        refetchOnWindowFocus: true,
        staleTime: 30_000,
        structuralSharing: expect.any(Function),
      },
    );
  });
});
