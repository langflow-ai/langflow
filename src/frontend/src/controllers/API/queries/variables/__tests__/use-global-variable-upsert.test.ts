const mockPostMutateAsync = jest.fn();
const mockPostMutate = jest.fn();
const mockPatchMutateAsync = jest.fn();
const mockPatchMutate = jest.fn();
const mockDeleteMutateAsync = jest.fn();
const mockDeleteMutate = jest.fn();

let mockGlobalVariables:
  | Array<{
      id: string;
      name: string;
      type?: string;
      default_fields?: string[];
      is_owner?: boolean;
    }>
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

import { act, renderHook } from "@testing-library/react";
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

      const { result } = renderHook(() => useGlobalVariableUpsert());
      let outcome: unknown;
      await act(async () => {
        outcome = await result.current.upsertGlobalVariable({
          name: "MY_VAR",
          value: "secret",
          type: "Credential",
          default_fields: ["System Message"],
        });
      });

      expect(mockPostMutateAsync).toHaveBeenCalledWith({
        name: "MY_VAR",
        value: "secret",
        type: "Credential",
        default_fields: ["System Message"],
        category: undefined,
      });
      expect(mockPatchMutateAsync).not.toHaveBeenCalled();
      expect(outcome).toEqual({
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

      const { result } = renderHook(() => useGlobalVariableUpsert());
      let outcome: unknown;
      await act(async () => {
        outcome = await result.current.upsertGlobalVariable({
          name: "MY_VAR",
          value: "new-value",
          default_fields: ["System Prompt"],
        });
      });

      expect(mockPatchMutateAsync).toHaveBeenCalledWith({
        id: "var-2",
        value: "new-value",
        default_fields: ["System Prompt"],
      });
      expect(mockPostMutateAsync).not.toHaveBeenCalled();
      expect(outcome).toEqual({
        action: "updated",
        name: "MY_VAR",
        id: "var-2",
      });
    });

    it("does not overwrite an existing variable of a different type: falls back to create so the backend rejects the duplicate name", async () => {
      mockGlobalVariables = [
        {
          id: "var-1",
          name: "SERVICE_URL",
          type: "Generic",
          default_fields: [],
        },
      ];
      mockPostMutateAsync.mockRejectedValue({
        response: { data: { detail: "Variable name already exists" } },
      });

      const { result } = renderHook(() => useGlobalVariableUpsert());

      await expect(
        result.current.upsertGlobalVariable({
          name: "SERVICE_URL",
          value: "secret",
          type: "Credential",
        }),
      ).rejects.toMatchObject({ action: "created" });

      expect(mockPatchMutateAsync).not.toHaveBeenCalled();
      expect(mockPostMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ name: "SERVICE_URL", type: "Credential" }),
      );
    });

    it("unions incoming default_fields with the existing list instead of replacing them", async () => {
      mockGlobalVariables = [
        {
          id: "var-2",
          name: "MY_VAR",
          type: "Credential",
          default_fields: ["System Message", "System Prompt", "Prefix"],
        },
      ];
      mockPatchMutateAsync.mockResolvedValue({ name: "MY_VAR" });

      const { result } = renderHook(() => useGlobalVariableUpsert());
      await act(async () => {
        await result.current.upsertGlobalVariable({
          name: "MY_VAR",
          value: "v",
          type: "Credential",
          default_fields: ["Suffix"],
        });
      });

      expect(mockPatchMutateAsync).toHaveBeenCalledWith({
        id: "var-2",
        value: "v",
        default_fields: ["System Message", "System Prompt", "Prefix", "Suffix"],
      });
    });

    it("falls back to create for a name owned by someone else, letting the backend decide", async () => {
      mockGlobalVariables = [
        {
          id: "var-9",
          name: "SHARED",
          type: "Credential",
          is_owner: false,
          default_fields: [],
        },
      ];
      mockPostMutateAsync.mockResolvedValue({ id: "var-10", name: "SHARED" });

      const { result } = renderHook(() => useGlobalVariableUpsert());
      let outcome: { action: string } | undefined;
      await act(async () => {
        outcome = await result.current.upsertGlobalVariable({
          name: "SHARED",
          value: "v",
          type: "Credential",
        });
      });

      expect(mockPatchMutateAsync).not.toHaveBeenCalled();
      expect(mockPostMutateAsync).toHaveBeenCalled();
      expect(outcome?.action).toBe("created");
    });

    it("omits default_fields from the update payload when not provided", async () => {
      mockGlobalVariables = [{ id: "var-1", name: "MY_VAR" }];
      mockPatchMutateAsync.mockResolvedValue({ name: "MY_VAR" });

      const { result } = renderHook(() => useGlobalVariableUpsert());
      await act(async () => {
        await result.current.upsertGlobalVariable({
          name: "MY_VAR",
          value: "v",
        });
      });

      expect(mockPatchMutateAsync).toHaveBeenCalledWith({
        id: "var-1",
        value: "v",
      });
    });

    it("matches names exactly (case-sensitive), like every existing wiring site", async () => {
      mockGlobalVariables = [{ id: "var-1", name: "my_var" }];
      mockPostMutateAsync.mockResolvedValue({ id: "var-2", name: "MY_VAR" });

      const { result } = renderHook(() => useGlobalVariableUpsert());
      let outcome: { action: string } | undefined;
      await act(async () => {
        outcome = await result.current.upsertGlobalVariable({
          name: "MY_VAR",
          value: "v",
        });
      });

      expect(mockPostMutateAsync).toHaveBeenCalled();
      expect(mockPatchMutateAsync).not.toHaveBeenCalled();
      expect(outcome?.action).toBe("created");
    });

    it("falls back to create when the variables list has not loaded (backend still rejects duplicates)", async () => {
      mockGlobalVariables = undefined;
      mockPostMutateAsync.mockResolvedValue({ id: "var-1", name: "MY_VAR" });

      const { result } = renderHook(() => useGlobalVariableUpsert());
      let outcome: { action: string } | undefined;
      await act(async () => {
        outcome = await result.current.upsertGlobalVariable({
          name: "MY_VAR",
          value: "v",
        });
      });

      expect(mockPostMutateAsync).toHaveBeenCalled();
      expect(outcome?.action).toBe("created");
    });

    it("propagates mutation errors to the caller", async () => {
      mockGlobalVariables = [];
      mockPostMutateAsync.mockRejectedValue(new Error("network"));

      const { result } = renderHook(() => useGlobalVariableUpsert());

      await expect(
        result.current.upsertGlobalVariable({ name: "MY_VAR", value: "v" }),
      ).rejects.toThrow("network");
    });
  });

  describe("passthroughs and pending state", () => {
    it("exposes the patch and delete mutations unchanged", () => {
      const { result } = renderHook(() => useGlobalVariableUpsert());

      expect(result.current.updateGlobalVariable).toBe(mockPatchMutate);
      expect(result.current.updateGlobalVariableAsync).toBe(
        mockPatchMutateAsync,
      );
      expect(result.current.deleteGlobalVariable).toBe(mockDeleteMutate);
      expect(result.current.deleteGlobalVariableAsync).toBe(
        mockDeleteMutateAsync,
      );
    });

    it("combines isPending across the three mutations", () => {
      const { result, rerender } = renderHook(() => useGlobalVariableUpsert());
      expect(result.current.isPending).toBe(false);

      mockPatchPending = true;
      rerender();
      expect(result.current.isPending).toBe(true);
      expect(result.current.isUpdating).toBe(true);
      expect(result.current.isCreating).toBe(false);
      expect(result.current.isDeleting).toBe(false);
    });
  });
});
