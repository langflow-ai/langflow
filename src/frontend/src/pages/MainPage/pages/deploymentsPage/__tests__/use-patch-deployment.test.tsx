import { act, renderHook, waitFor } from "@testing-library/react";
import { usePatchDeployment } from "@/controllers/API/queries/deployments/use-patch-deployment";
import { createTestWrapper } from "./test-utils";

// Mock the API module
const mockPatch = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: {
    patch: (...args: unknown[]) => mockPatch(...args),
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => {
    if (key === "DEPLOYMENTS") return "/api/v1/deployments";
    return `/${key}`;
  },
}));

// Mock UseRequestProcessor to provide real mutate/queryClient behavior
const mockRefetchQueries = jest.fn();
jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: () => ({
    mutate: (
      _key: string[],
      fn: (...args: unknown[]) => Promise<unknown>,
      options?: Record<string, unknown>,
    ) => {
      // Return a minimal useMutation-like object
      return {
        mutateAsync: async (variables: unknown) => {
          const result = await fn(variables);
          if (typeof options?.onSuccess === "function") {
            (options.onSuccess as (...args: unknown[]) => void)(result);
          }
          return result;
        },
        mutate: fn,
        isLoading: false,
        isPending: false,
      };
    },
    queryClient: {
      refetchQueries: mockRefetchQueries,
    },
  }),
}));

describe("usePatchDeployment", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("calls PATCH /api/v1/deployments/{id} with correct body", async () => {
    mockPatch.mockResolvedValue({
      data: { id: "deploy-1", name: "My Agent" },
    });

    const { result } = renderHook(() => usePatchDeployment());

    await act(async () => {
      await result.current.mutateAsync({
        deployment_id: "deploy-1",
        spec: { description: "Updated" },
      });
    });

    expect(mockPatch).toHaveBeenCalledWith(
      "/api/v1/deployments/deploy-1",
      { spec: { description: "Updated" } },
    );
  });

  it("strips deployment_id from the body (only used in URL)", async () => {
    mockPatch.mockResolvedValue({ data: { id: "deploy-1" } });

    const { result } = renderHook(() => usePatchDeployment());

    await act(async () => {
      await result.current.mutateAsync({
        deployment_id: "deploy-1",
        spec: { description: "New desc" },
        provider_data: { llm: "new-model" },
      });
    });

    const [, body] = mockPatch.mock.calls[0];
    expect(body).not.toHaveProperty("deployment_id");
    expect(body.spec).toEqual({ description: "New desc" });
    expect(body.provider_data).toEqual({ llm: "new-model" });
  });

  it("refetches deployments list on success", async () => {
    mockPatch.mockResolvedValue({ data: { id: "deploy-1" } });

    const { result } = renderHook(() => usePatchDeployment());

    await act(async () => {
      await result.current.mutateAsync({
        deployment_id: "deploy-1",
        spec: { description: "x" },
      });
    });

    expect(mockRefetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetDeployments"],
    });
  });

  it("sends add_flow_version_ids when provided", async () => {
    mockPatch.mockResolvedValue({ data: { id: "deploy-1" } });

    const { result } = renderHook(() => usePatchDeployment());

    await act(async () => {
      await result.current.mutateAsync({
        deployment_id: "deploy-1",
        add_flow_version_ids: ["ver-1", "ver-2"],
      });
    });

    const [, body] = mockPatch.mock.calls[0];
    expect(body.add_flow_version_ids).toEqual(["ver-1", "ver-2"]);
  });

  it("sends remove_flow_version_ids when provided", async () => {
    mockPatch.mockResolvedValue({ data: { id: "deploy-1" } });

    const { result } = renderHook(() => usePatchDeployment());

    await act(async () => {
      await result.current.mutateAsync({
        deployment_id: "deploy-1",
        remove_flow_version_ids: ["ver-old"],
      });
    });

    const [, body] = mockPatch.mock.calls[0];
    expect(body.remove_flow_version_ids).toEqual(["ver-old"]);
  });
});
