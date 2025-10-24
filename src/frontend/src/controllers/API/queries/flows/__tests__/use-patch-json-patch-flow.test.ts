// JSON Patch flow functionality tests

// Mock all dependencies before imports
const mockApiPatch = jest.fn();
const mockQueryClient = {
  refetchQueries: jest.fn(),
};

jest.mock("@/controllers/API/api", () => ({
  api: {
    patch: mockApiPatch,
  },
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: jest.fn((_key, fn, options) => ({
      mutate: async (payload: any) => {
        try {
          const result = await fn(payload);
          if (options?.onSettled) options.onSettled(result);
          return result;
        } catch (error) {
          if (options?.onSettled) options.onSettled(null);
          throw error;
        }
      },
    })),
    queryClient: mockQueryClient,
  })),
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn((key) => `/api/v1/${key.toLowerCase()}`),
}));

import { usePatchJsonPatchFlow } from "../use-patch-json-patch-flow";

describe("usePatchJsonPatchFlow", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("successful patch operations", () => {
    it("should successfully patch a flow with replace operation", async () => {
      const mockResponse = {
        data: {
          id: "flow-123",
          name: "Updated Flow Name",
          folder_id: "folder-456",
        },
      };
      mockApiPatch.mockResolvedValue(mockResponse);

      const mutation = usePatchJsonPatchFlow();
      const result = await mutation.mutate({
        id: "flow-123",
        operations: [
          { op: "replace", path: "/name", value: "Updated Flow Name" },
        ],
      });

      expect(mockApiPatch).toHaveBeenCalledWith(
        "/api/v1/flows/flow-123/json-patch",
        {
          operations: [
            { op: "replace", path: "/name", value: "Updated Flow Name" },
          ],
        },
      );
      expect(result).toEqual(mockResponse.data);
    });

    it("should successfully patch a flow with multiple operations", async () => {
      const mockResponse = {
        data: {
          id: "flow-123",
          name: "New Name",
          description: "New Description",
          folder_id: "folder-456",
        },
      };
      mockApiPatch.mockResolvedValue(mockResponse);

      const mutation = usePatchJsonPatchFlow();
      await mutation.mutate({
        id: "flow-123",
        operations: [
          { op: "replace", path: "/name", value: "New Name" },
          { op: "replace", path: "/description", value: "New Description" },
        ],
      });

      expect(mockApiPatch).toHaveBeenCalledWith(
        "/api/v1/flows/flow-123/json-patch",
        {
          operations: [
            { op: "replace", path: "/name", value: "New Name" },
            { op: "replace", path: "/description", value: "New Description" },
          ],
        },
      );
    });

    it("should refetch queries after successful patch", async () => {
      const mockResponse = {
        data: {
          id: "flow-123",
          name: "Updated Flow",
          folder_id: "folder-456",
        },
      };
      mockApiPatch.mockResolvedValue(mockResponse);

      const mutation = usePatchJsonPatchFlow();
      await mutation.mutate({
        id: "flow-123",
        operations: [{ op: "replace", path: "/name", value: "Updated Flow" }],
      });

      expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
        queryKey: ["useGetFolders", "folder-456"],
      });
      expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
        queryKey: ["useGetFolder"],
      });
    });
  });

  describe("different operation types", () => {
    it("should handle add operation", async () => {
      const mockResponse = {
        data: { id: "flow-123", tags: ["tag1"], folder_id: "folder-456" },
      };
      mockApiPatch.mockResolvedValue(mockResponse);

      const mutation = usePatchJsonPatchFlow();
      await mutation.mutate({
        id: "flow-123",
        operations: [{ op: "add", path: "/tags", value: ["tag1"] }],
      });

      expect(mockApiPatch).toHaveBeenCalledWith(
        "/api/v1/flows/flow-123/json-patch",
        {
          operations: [{ op: "add", path: "/tags", value: ["tag1"] }],
        },
      );
    });

    it("should handle remove operation", async () => {
      const mockResponse = {
        data: { id: "flow-123", folder_id: "folder-456" },
      };
      mockApiPatch.mockResolvedValue(mockResponse);

      const mutation = usePatchJsonPatchFlow();
      await mutation.mutate({
        id: "flow-123",
        operations: [{ op: "remove", path: "/endpoint_name" }],
      });

      expect(mockApiPatch).toHaveBeenCalledWith(
        "/api/v1/flows/flow-123/json-patch",
        {
          operations: [{ op: "remove", path: "/endpoint_name" }],
        },
      );
    });

    it("should handle move operation", async () => {
      const mockResponse = {
        data: { id: "flow-123", folder_id: "folder-456" },
      };
      mockApiPatch.mockResolvedValue(mockResponse);

      const mutation = usePatchJsonPatchFlow();
      await mutation.mutate({
        id: "flow-123",
        operations: [{ op: "move", from: "/tags/0", path: "/tags/1" }],
      });

      expect(mockApiPatch).toHaveBeenCalledWith(
        "/api/v1/flows/flow-123/json-patch",
        {
          operations: [{ op: "move", from: "/tags/0", path: "/tags/1" }],
        },
      );
    });

    it("should handle copy operation", async () => {
      const mockResponse = {
        data: { id: "flow-123", folder_id: "folder-456" },
      };
      mockApiPatch.mockResolvedValue(mockResponse);

      const mutation = usePatchJsonPatchFlow();
      await mutation.mutate({
        id: "flow-123",
        operations: [{ op: "copy", from: "/tags/0", path: "/tags/1" }],
      });

      expect(mockApiPatch).toHaveBeenCalledWith(
        "/api/v1/flows/flow-123/json-patch",
        {
          operations: [{ op: "copy", from: "/tags/0", path: "/tags/1" }],
        },
      );
    });

    it("should handle test operation", async () => {
      const mockResponse = {
        data: { id: "flow-123", folder_id: "folder-456" },
      };
      mockApiPatch.mockResolvedValue(mockResponse);

      const mutation = usePatchJsonPatchFlow();
      await mutation.mutate({
        id: "flow-123",
        operations: [{ op: "test", path: "/name", value: "Expected Name" }],
      });

      expect(mockApiPatch).toHaveBeenCalledWith(
        "/api/v1/flows/flow-123/json-patch",
        {
          operations: [{ op: "test", path: "/name", value: "Expected Name" }],
        },
      );
    });
  });

  describe("error handling", () => {
    it("should handle API errors", async () => {
      const mockError = new Error("Flow not found");
      mockApiPatch.mockRejectedValue(mockError);

      const mutation = usePatchJsonPatchFlow();
      await expect(
        mutation.mutate({
          id: "non-existent-flow",
          operations: [{ op: "replace", path: "/name", value: "New Name" }],
        }),
      ).rejects.toThrow("Flow not found");
    });

    it("should handle validation errors", async () => {
      const mockError = new Error("Invalid JSON Patch");
      mockApiPatch.mockRejectedValue(mockError);

      const mutation = usePatchJsonPatchFlow();
      await expect(
        mutation.mutate({
          id: "flow-123",
          operations: [{ op: "replace", path: "invalid-path", value: "value" }],
        }),
      ).rejects.toThrow("Invalid JSON Patch");
    });
  });
});
