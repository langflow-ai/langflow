const mockApiPost = jest.fn();
const mockApiPatch = jest.fn();
const mockApiDelete = jest.fn();
const mockRefetchQueries = jest.fn();

type MutationRegistration = {
  mutationFn: (variables: Record<string, unknown>) => Promise<unknown>;
  options: {
    onSettled?: (
      data: unknown,
      error: unknown,
      variables: Record<string, unknown>,
    ) => void;
  };
};

const mockMutationRegistrations = new Map<string, MutationRegistration>();

jest.mock("@/controllers/API/api", () => ({
  api: {
    post: (...args: unknown[]) => mockApiPost(...args),
    patch: (...args: unknown[]) => mockApiPatch(...args),
    delete: (...args: unknown[]) => mockApiDelete(...args),
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/variables",
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: () => ({
    mutate: (
      key: string[],
      mutationFn: MutationRegistration["mutationFn"],
      options: MutationRegistration["options"],
    ) => {
      mockMutationRegistrations.set(key[0], { mutationFn, options });
      return {};
    },
    queryClient: { refetchQueries: mockRefetchQueries },
  }),
}));

import { useDeleteGlobalVariables } from "../use-delete-global-variables";
import { usePatchGlobalVariables } from "../use-patch-global-variables";
import { usePostGlobalVariables } from "../use-post-global-variables";

const registeredMutation = (key: string): MutationRegistration => {
  const registration = mockMutationRegistrations.get(key);
  if (!registration) throw new Error(`Missing mutation registration: ${key}`);
  return registration;
};

describe("global-variable mutation scope", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockMutationRegistrations.clear();
  });

  it("creates in the requested flow and refetches only that scoped list", async () => {
    mockApiPost.mockResolvedValue({ data: { id: "var-1", name: "API_KEY" } });
    usePostGlobalVariables();
    const registration = registeredMutation("usePostGlobalVariables");
    const variables = {
      name: "API_KEY",
      value: "secret",
      type: "Credential",
      flowId: "flow-a",
    };

    await registration.mutationFn(variables);
    registration.options.onSettled?.({}, undefined, variables);

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/variables/?flow_id=flow-a",
      expect.not.objectContaining({ flowId: expect.anything() }),
    );
    expect(mockRefetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetGlobalVariables", "flow-a", undefined],
      exact: true,
    });
  });

  it("patches in the requested project and refetches only that scoped list", async () => {
    mockApiPatch.mockResolvedValue({ data: { id: "var-1", name: "API_KEY" } });
    usePatchGlobalVariables();
    const registration = registeredMutation("usePatchGlobalVariables");
    const variables = {
      id: "var-1",
      value: "replacement",
      projectId: "project-b",
    };

    await registration.mutationFn(variables);
    registration.options.onSettled?.({}, undefined, variables);

    expect(mockApiPatch).toHaveBeenCalledWith(
      "/api/v1/variables/var-1?project_id=project-b",
      { id: "var-1", value: "replacement" },
    );
    expect(mockRefetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetGlobalVariables", undefined, "project-b"],
      exact: true,
    });
  });

  it("deletes in the requested flow and refetches only that scoped list", async () => {
    mockApiDelete.mockResolvedValue(undefined);
    useDeleteGlobalVariables();
    const registration = registeredMutation("useDeleteGlobalVariables");
    const variables = { id: "var-1", flowId: "flow-c" };

    await registration.mutationFn(variables);
    registration.options.onSettled?.(undefined, undefined, variables);

    expect(mockApiDelete).toHaveBeenCalledWith(
      "/api/v1/variables/var-1?flow_id=flow-c",
    );
    expect(mockRefetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetGlobalVariables", "flow-c", undefined],
      exact: true,
    });
  });
});
