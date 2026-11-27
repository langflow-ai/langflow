import axios, { type InternalAxiosRequestConfig } from "axios";
import { usePostRenameFileV2 } from "../use-put-rename-file";

const mockMutate = jest.fn();
const mockInvalidate = jest.fn();
const mockAdapter = jest.fn();

// Exercise Axios URL handling without sending any network requests.
jest.mock("../../../api", () => ({
  api: jest.requireActual("axios").default.create({
    adapter: (config: InternalAxiosRequestConfig) => mockAdapter(config),
  }),
}));
jest.mock("../../../services/request-processor", () => ({
  UseRequestProcessor: () => ({
    mutate: mockMutate,
    queryClient: { invalidateQueries: mockInvalidate },
  }),
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockAdapter.mockImplementation(async (config) => ({
    data: { id: "7c483286-ccad-4a23-815d-fca987a3484a", name: "renamed" },
    status: 200,
    statusText: "OK",
    headers: {},
    config,
  }));
});

it.each([
  "R&D notes",
  "draft#2",
  "A+B",
  "计划 & review",
  "plain name",
  "100% complete",
  "literal%26name",
  "release%20notes & 计划+#2",
])("preserves the requested file name %s as one query value", async (name) => {
  usePostRenameFileV2();
  const [, mutation] = mockMutate.mock.calls[0];
  const result = await mutation({
    id: "7c483286-ccad-4a23-815d-fca987a3484a",
    name,
  });

  const [config] = mockAdapter.mock.calls[0];
  expect(config.method).toBe("put");
  const url = new URL(axios.getUri(config), "https://example.invalid");
  expect(url.pathname).toBe(
    "/api/v2/files/7c483286-ccad-4a23-815d-fca987a3484a",
  );
  expect([...url.searchParams.entries()]).toEqual([["name", name]]);
  expect(url.hash).toBe("");
  expect(result).toEqual({
    id: "7c483286-ccad-4a23-815d-fca987a3484a",
    name: "renamed",
  });
});

it("invalidates the file list after renaming", () => {
  usePostRenameFileV2();
  const [, , options] = mockMutate.mock.calls[0];
  options.onSettled();
  expect(mockInvalidate).toHaveBeenCalledWith({ queryKey: ["useGetFilesV2"] });
});
