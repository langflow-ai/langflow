const mockApiGet = jest.fn();
const mockSetTypes = jest.fn();
const mockRecomputeComponentsToUpdateIfNeeded = jest.fn();
const mockQuery = jest.fn((_key, fn, _options) => {
  const result = {
    data: null,
    isLoading: false,
    error: null,
  };
  fn()
    .then((data: unknown) => {
      result.data = data;
    })
    .catch((error: unknown) => {
      result.error = error;
    });
  return result;
});

const mockUseTypesStore = Object.assign(
  jest.fn((selector: (state: { setTypes: typeof mockSetTypes }) => unknown) =>
    selector({
      setTypes: mockSetTypes,
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

    useGetTypes();
    await Promise.resolve();
    await Promise.resolve();

    expect(mockSetTypes).toHaveBeenCalledWith(responseData);
    expect(mockRecomputeComponentsToUpdateIfNeeded).toHaveBeenCalledTimes(1);
  });

  it("scopes the palette request and cache key by flow", async () => {
    mockApiGet.mockResolvedValue({ data: {} });

    useGetTypes({ flowId: "flow-one" });
    await Promise.resolve();

    expect(mockApiGet).toHaveBeenCalledWith(
      "/api/v1/all?force_refresh=true&flow_id=flow-one",
    );
    expect(mockQuery).toHaveBeenCalledWith(
      ["useGetTypes", "flow-one", undefined],
      expect.any(Function),
      { refetchOnWindowFocus: false },
    );
  });
});
