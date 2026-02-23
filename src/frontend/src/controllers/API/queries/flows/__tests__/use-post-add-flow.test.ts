// usePostAddFlow hook tests

const mockApiPost = jest.fn();

const mockQueryClient = {
  refetchQueries: jest.fn(),
  invalidateQueries: jest.fn(),
};

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: jest.fn((selector: any) =>
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
    mutate: jest.fn((_key: any, fn: any, options: any) => ({
      mutate: async (payload: any) => {
        const result = await fn(payload);
        options?.onSettled?.(result);
        return result;
      },
    })),
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
});
