// useGetRefreshFlowsQuery hook tests — the queryFn writes the global flows
// store as a side effect, so a superseded (aborted) fetch must NEVER reach
// setFlows: a stale pre-creation list landing after a create+navigate makes
// FlowPage's existence guard bounce the user back to the list.

const mockApiGet = jest.fn();
const mockSetFlows = jest.fn();
const mockSetErrorData = jest.fn();
const mockTypesSetState = jest.fn();

let capturedQueryFn:
  | ((context: { signal?: AbortSignal }) => Promise<unknown>)
  | null = null;

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: jest.fn((selector: (state: unknown) => unknown) =>
    selector({ setFlows: mockSetFlows }),
  ),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: jest.fn((selector: (state: unknown) => unknown) =>
    selector({ setErrorData: mockSetErrorData }),
  ),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: {
    setState: (...args: unknown[]) => mockTypesSetState(...args),
  },
}));

jest.mock("@/utils/reactflowUtils", () => ({
  processFlows: jest.fn((flows: unknown[]) => ({ data: {}, flows })),
  extractSecretFieldsFromComponents: jest.fn(() => ({})),
}));

jest.mock("@/controllers/API/api", () => ({
  api: { get: mockApiGet },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn((key: string) => `/api/v1/${key.toLowerCase()}`),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    query: jest.fn(
      (_key: unknown, fn: typeof capturedQueryFn, _options: unknown) => {
        capturedQueryFn = fn;
        return { data: undefined, isLoading: false, error: null };
      },
    ),
    queryClient: {},
  })),
}));

import axios, { AxiosError } from "axios";
import { useGetRefreshFlowsQuery } from "../use-get-refresh-flows-query";

const FLOWS = [{ id: "flow-1" }, { id: "flow-2" }];

describe("useGetRefreshFlowsQuery", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedQueryFn = null;
  });

  it("forwards the query's AbortSignal to both HTTP calls and sets flows on success", async () => {
    mockApiGet
      .mockResolvedValueOnce({ data: FLOWS })
      .mockResolvedValueOnce({ data: [] });

    useGetRefreshFlowsQuery({ get_all: true, header_flows: true });
    const controller = new AbortController();
    const result = await capturedQueryFn!({ signal: controller.signal });

    expect(mockApiGet).toHaveBeenCalledTimes(2);
    expect(mockApiGet.mock.calls[0][1]).toEqual({ signal: controller.signal });
    expect(mockApiGet.mock.calls[1][1]).toEqual({ signal: controller.signal });
    expect(mockSetFlows).toHaveBeenCalledWith(FLOWS);
    expect(result).toEqual(FLOWS);
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("does not write the flows store or toast when the fetch is aborted", async () => {
    mockApiGet.mockRejectedValueOnce(new axios.CanceledError("canceled"));

    useGetRefreshFlowsQuery({ get_all: true, header_flows: true });
    await expect(capturedQueryFn!({ signal: undefined })).rejects.toThrow();

    expect(mockSetFlows).not.toHaveBeenCalled();
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("does not write the flows store or toast when the abort hits the second call", async () => {
    mockApiGet
      .mockResolvedValueOnce({ data: FLOWS })
      .mockRejectedValueOnce(new axios.CanceledError("canceled"));

    useGetRefreshFlowsQuery({ get_all: true, header_flows: true });
    await expect(capturedQueryFn!({ signal: undefined })).rejects.toThrow();

    expect(mockSetFlows).not.toHaveBeenCalled();
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("still toasts on a non-cancellation server error", async () => {
    const serverError = new AxiosError("boom");
    (serverError as AxiosError & { status?: number }).status = 500;
    mockApiGet.mockRejectedValueOnce(serverError);

    useGetRefreshFlowsQuery({ get_all: true, header_flows: true });
    await expect(capturedQueryFn!({ signal: undefined })).rejects.toThrow();

    expect(mockSetFlows).not.toHaveBeenCalled();
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "errors.couldNotLoadFlows",
    });
  });

  it("stays silent on 403 (auth-guarded fetch)", async () => {
    const forbidden = new AxiosError("forbidden");
    (forbidden as AxiosError & { status?: number }).status = 403;
    mockApiGet.mockRejectedValueOnce(forbidden);

    useGetRefreshFlowsQuery({ get_all: true, header_flows: true });
    await expect(capturedQueryFn!({ signal: undefined })).rejects.toThrow();

    expect(mockSetErrorData).not.toHaveBeenCalled();
  });
});
