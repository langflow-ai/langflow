const mockApiPatch = jest.fn();
const mockRefetchQueries = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { patch: mockApiPatch },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/projects"),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: () => ({
    mutate: (
      _key: unknown,
      mutationFn: (variables: unknown) => Promise<unknown>,
      options: { onSettled?: () => void },
    ) => ({
      mutate: async (variables: unknown) => {
        const result = await mutationFn(variables);
        options.onSettled?.();
        return result;
      },
    }),
    queryClient: { refetchQueries: mockRefetchQueries },
  }),
}));

import { usePatchFolders } from "../use-patch-folders";

describe("usePatchFolders", () => {
  beforeEach(() => jest.clearAllMocks());

  it("sends only editable project metadata with the observed strong revision", async () => {
    mockApiPatch.mockResolvedValue({
      data: { id: "project-1", name: "Renamed", edit_revision: 5 },
    });

    const mutation = usePatchFolders();
    const result = await mutation.mutate({
      folderId: "project-1",
      editRevision: 4,
      data: { name: "Renamed", description: "Updated" },
    });

    expect(mockApiPatch).toHaveBeenCalledWith(
      "/api/v1/projects/project-1",
      { name: "Renamed", description: "Updated" },
      { headers: { "If-Match": '"project:project-1:4"' } },
    );
    expect(result).toEqual({
      id: "project-1",
      name: "Renamed",
      edit_revision: 5,
    });
  });
});
