import { usePostUploadFlows } from "../use-post-upload-flows";

const mockApiPost = jest.fn();
const mockRefetch = jest.fn();
const mockQueryClient = {
  refetchQueries: mockRefetch,
  invalidateQueries: jest.fn(),
  getQueryCache: jest.fn(() => ({ findAll: jest.fn(() => []) })),
};

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: (selector: (state: unknown) => unknown) =>
    selector({ myCollectionId: "default-project" }),
}));
jest.mock("@/controllers/API/api", () => ({
  api: { post: (...args: unknown[]) => mockApiPost(...args) },
}));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `/api/v1/${key.toLowerCase()}`,
}));
jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: () => ({
    mutate: (
      _key: unknown,
      mutation: (payload: unknown) => Promise<unknown>,
      options: { onSettled: (data: unknown) => void },
    ) => ({
      mutateAsync: async (payload: unknown) => {
        const data = await mutation(payload);
        options.onSettled(data);
        return data;
      },
    }),
    queryClient: mockQueryClient,
  }),
}));

const payload = {
  name: "Imported",
  description: "Description",
  data: { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
  is_component: false,
  folder_id: "project",
  endpoint_name: undefined,
  icon: undefined,
  gradient: undefined,
  tags: ["tag"],
  locked: true,
  mcp_enabled: true,
};

const readFile = (file: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsText(file);
  });

describe("combined flow upload request", () => {
  beforeEach(() => jest.clearAllMocks());

  it("posts every flow in one JSON file without imported IDs", async () => {
    mockApiPost.mockResolvedValue({
      data: [
        { id: "created-1", folder_id: "project" },
        { id: "created-2", folder_id: "project" },
      ],
    });
    const mutation = usePostUploadFlows();
    const flows = [
      { ...payload, id: "existing-1" },
      { ...payload, name: "Second", id: "existing-2" },
    ];

    await mutation.mutateAsync(flows);

    expect(mockApiPost).toHaveBeenCalledTimes(1);
    const [url, body] = mockApiPost.mock.calls[0];
    expect(url).toBe("/api/v1/flows/upload/");
    const contents = JSON.parse(await readFile(body.get("file")));
    expect(contents.flows).toHaveLength(2);
    expect(contents.flows[0]).toMatchObject({
      name: "Imported",
      folder_id: "project",
      locked: true,
      tags: ["tag"],
    });
    expect(contents.flows[1]).toMatchObject({
      name: "Second",
      folder_id: "project",
    });
    expect(
      contents.flows.every((flow: { id?: string }) => flow.id === undefined),
    ).toBe(true);
    expect(mockRefetch).toHaveBeenCalledTimes(2);
    expect(mockRefetch).toHaveBeenCalledWith({
      queryKey: ["useGetFolder", "project"],
    });
  });

  it("propagates a refusal without refreshing the flow lists", async () => {
    const error = {
      response: { status: 422, data: { detail: "Too many triggers" } },
    };
    mockApiPost.mockRejectedValue(error);
    const mutation = usePostUploadFlows();

    await expect(mutation.mutateAsync([payload])).rejects.toBe(error);

    expect(mockApiPost).toHaveBeenCalledTimes(1);
    expect(mockRefetch).not.toHaveBeenCalled();
  });
});
