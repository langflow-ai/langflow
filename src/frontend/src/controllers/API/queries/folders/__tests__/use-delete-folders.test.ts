const mockApiDelete = jest.fn();
const mockSetFolders = jest.fn();
const mockRefetchQueries = jest.fn();
const mockInvalidateQueries = jest.fn();

const folderState = {
  folders: [
    { id: "project-1", name: "First" },
    { id: "project-2", name: "Second" },
  ],
  setFolders: mockSetFolders,
};

jest.mock("@/controllers/API/api", () => ({
  api: { delete: mockApiDelete },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/projects"),
}));

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: (selector: (state: typeof folderState) => unknown) =>
    selector(folderState),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: () => ({
    mutate: (
      _key: unknown,
      mutationFn: (variables: unknown) => Promise<unknown>,
      options: { onSettled?: (result: unknown) => void },
    ) => ({
      mutate: async (variables: unknown) => {
        const result = await mutationFn(variables);
        options.onSettled?.(result);
        return result;
      },
    }),
    queryClient: {
      refetchQueries: mockRefetchQueries,
      invalidateQueries: mockInvalidateQueries,
    },
  }),
}));

import { useDeleteFolders } from "../use-delete-folders";

describe("useDeleteFolders", () => {
  beforeEach(() => jest.clearAllMocks());

  it("deletes with the observed strong revision and updates local folders", async () => {
    mockApiDelete.mockResolvedValue({ status: 204 });

    const mutation = useDeleteFolders();
    const result = await mutation.mutate({
      folder_id: "project-1",
      edit_revision: 9,
    });

    expect(mockApiDelete).toHaveBeenCalledWith("/api/v1/projects/project-1", {
      headers: { "If-Match": '"project:project-1:9"' },
    });
    expect(mockSetFolders).toHaveBeenCalledWith([
      { id: "project-2", name: "Second" },
    ]);
    expect(result).toBe("project-1");
  });
});
