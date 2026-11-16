import { act, renderHook } from "@testing-library/react";
import { useFolderStore } from "@/stores/foldersStore";

const mockApiGet = jest.fn();
let capturedQueryFn: (() => Promise<unknown>) | undefined;

jest.mock("@/controllers/API/api", () => ({
  api: { get: mockApiGet },
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: () => ({
    query: (_key: unknown, queryFn: () => Promise<unknown>) => {
      capturedQueryFn = queryFn;
      return {};
    },
  }),
}));

import { useGetFolderQuery } from "../use-get-folder";

const EXISTING_PROJECT_ID = "5f9b0f2e-0d5e-4f6a-9d3f-2b6f7f0a1c22";
const DELETED_PROJECT_ID = "b1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e";

const SECOND_PROJECT_ID = "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d";

const paramsFor = (id: string | null | undefined, page = 1) => ({
  id,
  page,
  size: 12,
  is_component: false,
  is_flow: true,
  search: "",
});

const runQuery = async (id: string | null | undefined, page = 1) => {
  renderHook(() => useGetFolderQuery(paramsFor(id, page)));

  let result: unknown;
  await act(async () => {
    result = await capturedQueryFn?.();
  });
  return result;
};

describe("useGetFolderQuery", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedQueryFn = undefined;
    useFolderStore.setState({
      folders: [
        { id: EXISTING_PROJECT_ID, name: "Starter Project" },
        { id: SECOND_PROJECT_ID, name: "Second Project" },
      ] as never,
    });
  });

  it.each([
    ["undefined", undefined],
    ["null", null],
    ["empty", ""],
  ])(
    "sends no request and resolves with null when the project id is %s",
    async (_label, id) => {
      const result = await runQuery(id);

      expect(mockApiGet).not.toHaveBeenCalled();
      expect(result).toBeNull();
    },
  );

  it("sends no request and resolves with null for a project the store no longer lists", async () => {
    const result = await runQuery(DELETED_PROJECT_ID);

    expect(mockApiGet).not.toHaveBeenCalled();
    expect(result).toBeNull();
  });

  it("requests the project the store still lists", async () => {
    mockApiGet.mockResolvedValue({
      data: { folder: { id: EXISTING_PROJECT_ID }, flows: { items: [] } },
    });

    await runQuery(EXISTING_PROJECT_ID);

    expect(mockApiGet).toHaveBeenCalledTimes(1);
    const requestedUrl = mockApiGet.mock.calls[0][0] as string;
    expect(requestedUrl).toContain(`/projects/${EXISTING_PROJECT_ID}?`);
    expect(requestedUrl).not.toContain("undefined");
  });

  it("requests the page it is given after the project changes", async () => {
    mockApiGet.mockResolvedValue({
      data: { folder: { id: SECOND_PROJECT_ID }, flows: { items: [] } },
    });

    await runQuery(EXISTING_PROJECT_ID, 2);
    await runQuery(SECOND_PROJECT_ID, 2);

    const secondProjectUrl = mockApiGet.mock.calls[1][0] as string;
    expect(secondProjectUrl).toContain(`/projects/${SECOND_PROJECT_ID}?`);
    expect(secondProjectUrl).toContain("page=2");
  });
});
