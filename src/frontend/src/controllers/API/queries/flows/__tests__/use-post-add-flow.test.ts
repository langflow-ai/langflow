// usePostAddFlow hook tests

const mockApiPost = jest.fn();

const mockQueryClient = {
  refetchQueries: jest.fn(),
  invalidateQueries: jest.fn(),
  getQueryCache: jest.fn(() => ({ findAll: jest.fn(() => []) })),
};

type FolderStoreState = { myCollectionId: string };
type MockMutationFn = (payload: unknown) => Promise<unknown>;
type MockMutationOptions = {
  onSettled?: (result: unknown) => void | Promise<void>;
};

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: jest.fn((selector: (state: FolderStoreState) => unknown) =>
    selector({ myCollectionId: "mc" }),
  ),
}));

jest.mock("@/controllers/API/api", () => ({
  api: {
    post: mockApiPost,
  },
}));

import { usePostAddFlow } from "../use-post-add-flow";

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn((key: string) => `/api/v1/${key.toLowerCase()}`),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: jest.fn(
      (_key: unknown, fn: MockMutationFn, options: MockMutationOptions) => ({
        mutate: async (payload: unknown) => {
          const result = await fn(payload);
          await options?.onSettled?.(result);
          return result;
        },
      }),
    ),
    queryClient: mockQueryClient,
  })),
}));

describe("usePostAddFlow", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("posts locked when provided", async () => {
    mockApiPost.mockResolvedValue({ data: { id: "new-flow" } });

    const mutation = usePostAddFlow();

    await mutation.mutate({
      name: "Flow",
      description: "Desc",
      data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
      is_component: false,
      folder_id: "folder",
      endpoint_name: undefined,
      icon: undefined,
      gradient: undefined,
      tags: [],
      locked: true,
      mcp_enabled: true,
    });

    expect(mockApiPost).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/flows/"),
      expect.objectContaining({ locked: true }),
    );
  });

  it("sends locked null when not provided", async () => {
    mockApiPost.mockResolvedValue({ data: { id: "new-flow" } });

    const mutation = usePostAddFlow();

    await mutation.mutate({
      name: "Flow",
      description: "Desc",
      data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
      is_component: false,
      folder_id: "folder",
      endpoint_name: undefined,
      icon: undefined,
      gradient: undefined,
      tags: [],
      mcp_enabled: true,
    });

    expect(mockApiPost).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/flows/"),
      expect.objectContaining({ locked: null }),
    );
  });

  it("refetches the created flow's project list", async () => {
    mockApiPost.mockResolvedValue({
      data: { id: "new-flow", folder_id: "folder" },
    });

    const mutation = usePostAddFlow();

    await mutation.mutate({
      name: "Flow",
      description: "Desc",
      data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
      is_component: false,
      folder_id: "folder",
      endpoint_name: undefined,
      icon: undefined,
      gradient: undefined,
      tags: [],
      mcp_enabled: true,
    });

    expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetFolder", "folder"],
    });
    expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: [
        "useGetRefreshFlowsQuery",
        { get_all: true, header_flows: true },
      ],
    });
  });
});
