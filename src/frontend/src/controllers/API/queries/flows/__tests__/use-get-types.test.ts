const mockApiGet = jest.fn();
const mockSetTypes = jest.fn();
const mockRecomputeComponentsToUpdateIfNeeded = jest.fn();

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
    query: jest.fn((_key, fn, _options) => {
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
    }),
  })),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  recomputeComponentsToUpdateIfNeeded: mockRecomputeComponentsToUpdateIfNeeded,
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
});
