const mockApiPost = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { post: mockApiPost },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/build"),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: jest.fn(
      (_key: unknown, fn: (payload: unknown) => Promise<unknown>) => ({
        mutate: (payload: unknown) => fn(payload),
      }),
    ),
  })),
}));

import { usePostRetrieveVertexOrder } from "../use-post-retrieve-vertex-order";

describe("usePostRetrieveVertexOrder", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiPost.mockResolvedValue({
      data: { ids: [], rund_id: "run", vertices_to_run: [] },
    });
  });

  it("passes percent sequences in stop node IDs to the request serializer unchanged", async () => {
    const mutation = usePostRetrieveVertexOrder();

    await mutation.mutate({
      flowId: "flow-1",
      stopNodeId: "node%252Fencoded",
    });

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/build/flow-1/vertices",
      null,
      { params: { stop_component_id: "node%252Fencoded" } },
    );
  });

  it("passes malformed percent sequences in start node IDs unchanged", async () => {
    const mutation = usePostRetrieveVertexOrder();

    await mutation.mutate({
      flowId: "flow-1",
      startNodeId: "node%invalid",
    });

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/build/flow-1/vertices",
      null,
      { params: { start_component_id: "node%invalid" } },
    );
  });
});
