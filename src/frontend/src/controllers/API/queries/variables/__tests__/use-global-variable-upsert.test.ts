const mockPostMutateAsync = jest.fn();
const mockPostMutate = jest.fn();
const mockPatchMutateAsync = jest.fn();
const mockPatchMutate = jest.fn();
const mockDeleteMutateAsync = jest.fn();
const mockDeleteMutate = jest.fn();

let mockGlobalVariables:
  | Array<{ id: string; name: string; type?: string }>
  | undefined;
let mockPostPending = false;
let mockPatchPending = false;
let mockDeletePending = false;

jest.mock("../use-get-global-variables", () => ({
  useGetGlobalVariables: () => ({ data: mockGlobalVariables }),
}));

jest.mock("../use-post-global-variables", () => ({
  usePostGlobalVariables: () => ({
    mutate: mockPostMutate,
    mutateAsync: mockPostMutateAsync,
    isPending: mockPostPending,
  }),
}));

jest.mock("../use-patch-global-variables", () => ({
  usePatchGlobalVariables: () => ({
    mutate: mockPatchMutate,
    mutateAsync: mockPatchMutateAsync,
    isPending: mockPatchPending,
  }),
}));

jest.mock("../use-delete-global-variables", () => ({
  useDeleteGlobalVariables: () => ({
    mutate: mockDeleteMutate,
    mutateAsync: mockDeleteMutateAsync,
    isPending: mockDeletePending,
  }),
}));

import { useGlobalVariableUpsert } from "../use-global-variable-upsert";

describe("useGlobalVariableUpsert", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGlobalVariables = [];
    mockPostPending = false;
    mockPatchPending = false;
    mockDeletePending = false;
  });

  describe("upsertGlobalVariable", () => {
    it("creates the variable when the name does not exist", async () => {
      mockGlobalVariables = [{ id: "var-1", name: "OPENAI_API_KEY" }];
      mockPostMutateAsync.mockResolvedValue({
        id: "var-2",
        name: "MY_VAR",
        type: "Credential",
      });

      const { upsertGlobalVariable } = useGlobalVariableUpsert();
      const result = await upsertGlobalVariable({
        name: "MY_VAR",
        value: "secret",
        type: "Credential",
        default_fields: ["System Message"],
      });

      expect(mockPostMutateAsync).toHaveBeenCalledWith({
        name: "MY_VAR",
        value: "secret",
        type: "Credential",
        default_fields: ["System Message"],
        category: undefined,
      });
      expect(mockPatchMutateAsync).not.toHaveBeenCalled();
      expect(result).toEqual({
        action: "created",
        name: "MY_VAR",
        id: "var-2",
      });
    });

    it("updates the existing variable when the name already exists, never creating a duplicate", async () => {
      mockGlobalVariables = [
        { id: "var-1", name: "OPENAI_API_KEY" },
        { id: "var-2", name: "MY_VAR" },
      ];
      mockPatchMutateAsync.mockResolvedValue({ name: "MY_VAR" });

      const { upsertGlobalVariable } = useGlobalVariableUpsert();
      const result = await upsertGlobalVariable({
        name: "MY_VAR",
        value: "new-value",
        default_fields: ["System Prompt"],
      });

      expect(mockPatchMutateAsync).toHaveBeenCalledWith({
        id: "var-2",
        value: "new-value",
        default_fields: ["System Prompt"],
      });
      expect(mockPostMutateAsync).not.toHaveBeenCalled();
      expect(result).toEqual({
        action: "updated",
        name: "MY_VAR",
        id: "var-2",
      });
    });

    it("omits default_fields from the update payload when not provided", async () => {
      mockGlobalVariables = [{ id: "var-1", name: "MY_VAR" }];
      mockPatchMutateAsync.mockResolvedValue({ name: "MY_VAR" });

      const { upsertGlobalVariable } = useGlobalVariableUpsert();
      await upsertGlobalVariable({ name: "MY_VAR", value: "v" });

      expect(mockPatchMutateAsync).toHaveBeenCalledWith({
        id: "var-1",
        value: "v",
      });
    });

    it("matches names exactly (case-sensitive), like every existing wiring site", async () => {
      mockGlobalVariables = [{ id: "var-1", name: "my_var" }];
      mockPostMutateAsync.mockResolvedValue({ id: "var-2", name: "MY_VAR" });

      const { upsertGlobalVariable } = useGlobalVariableUpsert();
      const result = await upsertGlobalVariable({ name: "MY_VAR", value: "v" });

      expect(mockPostMutateAsync).toHaveBeenCalled();
      expect(mockPatchMutateAsync).not.toHaveBeenCalled();
      expect(result.action).toBe("created");
    });

    it("falls back to create when the variables list has not loaded (backend still rejects duplicates)", async () => {
      mockGlobalVariables = undefined;
      mockPostMutateAsync.mockResolvedValue({ id: "var-1", name: "MY_VAR" });

      const { upsertGlobalVariable } = useGlobalVariableUpsert();
      const result = await upsertGlobalVariable({ name: "MY_VAR", value: "v" });

      expect(mockPostMutateAsync).toHaveBeenCalled();
      expect(result.action).toBe("created");
    });

    it("propagates mutation errors to the caller", async () => {
      mockGlobalVariables = [];
      mockPostMutateAsync.mockRejectedValue(new Error("network"));

      const { upsertGlobalVariable } = useGlobalVariableUpsert();

      await expect(
        upsertGlobalVariable({ name: "MY_VAR", value: "v" }),
      ).rejects.toThrow("network");
    });
  });

  describe("passthroughs and pending state", () => {
    it("exposes the patch and delete mutations unchanged", () => {
      const hook = useGlobalVariableUpsert();

      expect(hook.updateGlobalVariable).toBe(mockPatchMutate);
      expect(hook.updateGlobalVariableAsync).toBe(mockPatchMutateAsync);
      expect(hook.deleteGlobalVariable).toBe(mockDeleteMutate);
      expect(hook.deleteGlobalVariableAsync).toBe(mockDeleteMutateAsync);
    });

    it("combines isPending across the three mutations", () => {
      expect(useGlobalVariableUpsert().isPending).toBe(false);

      mockPatchPending = true;
      const pending = useGlobalVariableUpsert();
      expect(pending.isPending).toBe(true);
      expect(pending.isUpdating).toBe(true);
      expect(pending.isCreating).toBe(false);
      expect(pending.isDeleting).toBe(false);
    });
  });
});
