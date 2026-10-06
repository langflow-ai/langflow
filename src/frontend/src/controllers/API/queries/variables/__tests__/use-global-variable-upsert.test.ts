import type { GlobalVariable } from "@/types/global_variables";

const mockPostMutateAsync = jest.fn();
const mockPostMutate = jest.fn();
const mockPatchMutateAsync = jest.fn();
const mockPatchMutate = jest.fn();
const mockUseGetGlobalVariablesHook = jest.fn((_options?: unknown) => ({
  data: mockGlobalVariables,
}));

type MockGlobalVariable = Pick<GlobalVariable, "id" | "name"> &
  Partial<GlobalVariable>;

let mockGlobalVariables: MockGlobalVariable[] | undefined;

const resolvedMockGlobalVariables = (): GlobalVariable[] | undefined =>
  mockGlobalVariables?.map((variable) => ({
    type: "Credential",
    default_fields: [],
    ...variable,
  }));

jest.mock("../use-get-global-variables", () => ({
  useGetGlobalVariables: (options?: unknown) =>
    mockUseGetGlobalVariablesHook(options),
}));

jest.mock("../use-post-global-variables", () => ({
  usePostGlobalVariables: () => ({
    mutate: mockPostMutate,
    mutateAsync: mockPostMutateAsync,
  }),
}));

jest.mock("../use-patch-global-variables", () => ({
  usePatchGlobalVariables: () => ({
    mutate: mockPatchMutate,
    mutateAsync: mockPatchMutateAsync,
  }),
}));

import { act, renderHook } from "@testing-library/react";
import type { ProviderScopeParams } from "../../../helpers/provider-scope";
import { useGlobalVariableUpsert } from "../use-global-variable-upsert";

const renderUpsertHook = (providerScope?: ProviderScopeParams) =>
  renderHook(() =>
    useGlobalVariableUpsert(providerScope, resolvedMockGlobalVariables()),
  );

describe("useGlobalVariableUpsert", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGlobalVariables = [];
  });

  describe("upsertGlobalVariable", () => {
    it("creates the variable when the name does not exist", async () => {
      mockGlobalVariables = [{ id: "var-1", name: "OPENAI_API_KEY" }];
      mockPostMutateAsync.mockResolvedValue({
        id: "var-2",
        name: "MY_VAR",
        type: "Credential",
      });

      const { result } = renderUpsertHook();
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

      const { result } = renderUpsertHook();
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

      const { result } = renderUpsertHook();

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

      const { result } = renderUpsertHook();
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

      const { result } = renderUpsertHook();
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

      const { result } = renderUpsertHook();
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

      const { result } = renderUpsertHook();
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

      const { result } = renderUpsertHook();
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

      const { result } = renderUpsertHook();

      await expect(
        result.current.upsertGlobalVariable({ name: "MY_VAR", value: "v" }),
      ).rejects.toThrow("network");
    });
  });

  describe("passthroughs", () => {
    it("forwards updateGlobalVariable to patch without adding scope", () => {
      const options = { onSuccess: jest.fn() };
      const { result } = renderUpsertHook();

      result.current.updateGlobalVariable(
        { id: "var-1", name: "MY_VAR" },
        options,
      );

      expect(mockPatchMutate).toHaveBeenCalledWith(
        { id: "var-1", name: "MY_VAR" },
        options,
      );
    });
  });

  describe("provider scope", () => {
    const providerScope = { flowId: "flow-project-a" };

    it("uses the same trusted flow scope for the lookup and create", async () => {
      mockPostMutateAsync.mockResolvedValue({
        id: "var-2",
        name: "PROJECT_KEY",
      });

      const { result } = renderUpsertHook(providerScope);
      await act(async () => {
        await result.current.upsertGlobalVariable({
          name: "PROJECT_KEY",
          value: "secret",
          type: "Credential",
        });
      });

      expect(mockUseGetGlobalVariablesHook).not.toHaveBeenCalled();
      expect(mockPostMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining(providerScope),
      );
    });

    it("uses the trusted flow scope for an existing variable update", async () => {
      mockGlobalVariables = [{ id: "var-1", name: "PROJECT_KEY" }];
      mockPatchMutateAsync.mockResolvedValue({ name: "PROJECT_KEY" });

      const { result } = renderUpsertHook(providerScope);
      await act(async () => {
        await result.current.upsertGlobalVariable({
          name: "PROJECT_KEY",
          value: "replacement",
        });
      });

      expect(mockPatchMutateAsync).toHaveBeenCalledWith({
        id: "var-1",
        value: "replacement",
        ...providerScope,
      });
    });

    it("binds the trusted flow scope to edit-path updates", () => {
      const options = { onSuccess: jest.fn() };
      const { result } = renderUpsertHook(providerScope);

      result.current.updateGlobalVariable(
        { id: "var-1", name: "PROJECT_KEY" },
        options,
      );

      expect(mockPatchMutate).toHaveBeenCalledWith(
        { id: "var-1", name: "PROJECT_KEY", ...providerScope },
        options,
      );
    });
  });
});
