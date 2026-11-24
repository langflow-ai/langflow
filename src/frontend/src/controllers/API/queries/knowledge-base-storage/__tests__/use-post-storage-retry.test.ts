import { usePostStorageRetry } from "../use-post-storage-retry";

const mockPost = jest.fn();
const mockMutate = jest.fn();
const mockInvalidate = jest.fn();

jest.mock("../../../api", () => ({
  api: { post: (...args) => mockPost(...args) },
}));
jest.mock("../../../helpers/constants", () => ({
  getURL: () => "/api/v1/knowledge-base-storage",
}));
jest.mock("../../../services/request-processor", () => ({
  UseRequestProcessor: () => ({
    mutate: mockMutate,
    queryClient: { invalidateQueries: mockInvalidate },
  }),
}));

beforeEach(() => jest.clearAllMocks());

it.each([
  [{ migrationId: "migration-id" }, "migrations/migration-id/retry"],
  [{ inventory: true }, "inventory/retry"],
])("schedules the requested storage recovery at %s", async (request, path) => {
  mockPost.mockResolvedValue({ data: { status: "scheduled" } });
  usePostStorageRetry();
  const [, mutation, options] = mockMutate.mock.calls[0];
  expect(await mutation(request)).toEqual({ status: "scheduled" });
  expect(mockPost).toHaveBeenCalledWith(
    `/api/v1/knowledge-base-storage/${path}`,
  );
  options.onSettled();
  expect(mockInvalidate).toHaveBeenCalledWith({
    queryKey: ["useGetStorageStatus"],
  });
  expect(options.retry).toBe(false);
});
