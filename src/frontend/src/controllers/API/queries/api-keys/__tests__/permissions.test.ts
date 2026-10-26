const mockGet = jest.fn();
const mockPatch = jest.fn();
const mockInvalidate = jest.fn();
const mockQuery = jest.fn();
const mockMutate = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
    patch: (...args: unknown[]) => mockPatch(...args),
  },
}));
jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: () => ({
    query: mockQuery,
    mutate: mockMutate,
    queryClient: { invalidateQueries: mockInvalidate },
  }),
}));
jest.mock("@/customization/utils/urls", () => ({
  getBaseUrl: () => "/api/v1/",
}));

import { useGetApiKeyPermissionOptions } from "../use-get-api-key-permission-options";
import { getApiKeyPermissionTargets } from "../use-get-api-key-permission-targets";
import { usePatchApiKeyPermissions } from "../use-patch-api-key-permissions";

describe("API key permission requests", () => {
  beforeEach(() => jest.clearAllMocks());

  it("returns the current eligible permission options", async () => {
    const options = {
      supported: true,
      roles: [],
      resource_actions: { flow: ["read"] },
      scope_types: { flow: ["global"] },
    };
    mockGet.mockResolvedValue({ data: options });
    useGetApiKeyPermissionOptions();
    const query = mockQuery.mock.calls[0][1];
    await expect(query()).resolves.toEqual(options);
    expect(mockGet).toHaveBeenCalledWith("/api/v1/api_key/permission-options");
    expect(mockQuery.mock.calls[0][2]).toMatchObject({ retry: false });
  });

  it.each([404, 501])(
    "keeps older backends compatible on HTTP %s",
    async (status) => {
      mockGet.mockRejectedValue({ response: { status } });
      useGetApiKeyPermissionOptions();
      await expect(mockQuery.mock.calls[0][1]()).resolves.toMatchObject({
        supported: false,
      });
    },
  );

  it.each([401, 403, 500])(
    "does not silently downgrade on HTTP %s",
    async (status) => {
      const error = { response: { status } };
      mockGet.mockRejectedValue(error);
      useGetApiKeyPermissionOptions();
      await expect(mockQuery.mock.calls[0][1]()).rejects.toBe(error);
    },
  );

  it("patches the full permission policy without rotating a secret", async () => {
    const permissions = {
      roles: [{ role_id: "viewer", domain_type: "global", domain_id: null }],
      restrictions: [],
    };
    mockPatch.mockResolvedValue({ data: { id: "key-a", permissions } });
    usePatchApiKeyPermissions();
    await expect(
      mockMutate.mock.calls[0][1]({ id: "key-a", permissions }),
    ).resolves.toMatchObject({ id: "key-a", permissions });
    expect(mockPatch).toHaveBeenCalledWith(
      "/api/v1/api_key/key-a/permissions",
      { permissions },
    );
    expect(mockMutate.mock.calls[0][2]).toMatchObject({ retry: false });
  });

  it("invalidates key metadata after a permission change", () => {
    const onSettled = jest.fn();
    usePatchApiKeyPermissions({ onSettled });
    mockMutate.mock.calls[0][2].onSettled(undefined, null, {
      id: "key-a",
      permissions: null,
    });
    expect(mockInvalidate).toHaveBeenCalledWith({
      queryKey: ["useGetApiKeysQuery"],
    });
    expect(onSettled).toHaveBeenCalled();
  });

  it("uses project names from the authorized project endpoint", async () => {
    mockGet.mockResolvedValue({ data: [{ id: "a", name: "Project A" }] });
    await expect(getApiKeyPermissionTargets("project")).resolves.toEqual([
      { id: "a", name: "Project A" },
    ]);
    expect(mockGet).toHaveBeenCalledWith("/api/v1/projects/");
  });

  it("uses the canonical knowledge-base identifier", async () => {
    mockGet.mockResolvedValue({
      data: [
        {
          id: "metadata-id",
          dir_name: "knowledge-base-name",
          name: "Knowledge base",
        },
      ],
    });
    await expect(getApiKeyPermissionTargets("knowledge_base")).resolves.toEqual(
      [{ id: "metadata-id", name: "Knowledge base" }],
    );
  });

  it("does not invent collection endpoints for unsupported resource types", async () => {
    await expect(getApiKeyPermissionTargets("voice")).resolves.toEqual([]);
    expect(mockGet).not.toHaveBeenCalled();
  });

  it.each(["flow", "variable", "file", "connection"])(
    "uses authorized %s resource metadata",
    async (resourceType) => {
      mockGet.mockResolvedValue({
        data: [{ id: "resource-a", name: "Resource A" }],
      });
      await expect(getApiKeyPermissionTargets(resourceType)).resolves.toEqual([
        { id: "resource-a", name: "Resource A" },
      ]);
    },
  );

  it("accepts paginated flow response shapes", async () => {
    mockGet.mockResolvedValue({
      data: { items: [{ id: "flow-a", name: "Flow A" }] },
    });
    await expect(getApiKeyPermissionTargets("flow")).resolves.toEqual([
      { id: "flow-a", name: "Flow A" },
    ]);
    expect(mockGet).toHaveBeenCalledWith("/api/v1/flows/", {
      params: { get_all: true, header_flows: true },
    });
  });

  it("uses canonical knowledge-base IDs even when names collide", async () => {
    mockGet.mockResolvedValue({
      data: [
        { id: "kb-owner-a", name: "Shared name", dir_name: "shared_name" },
        { id: "kb-owner-b", name: "Shared name", dir_name: "shared_name" },
      ],
    });
    await expect(getApiKeyPermissionTargets("knowledge_base")).resolves.toEqual(
      [
        { id: "kb-owner-a", name: "Shared name" },
        { id: "kb-owner-b", name: "Shared name" },
      ],
    );
  });

  it("loads every provider-account page", async () => {
    mockGet
      .mockResolvedValueOnce({
        data: {
          provider_accounts: [{ id: "provider-a", name: "A" }],
          total: 2,
        },
      })
      .mockResolvedValueOnce({
        data: {
          provider_accounts: [{ id: "provider-b", name: "B" }],
          total: 2,
        },
      });
    await expect(
      getApiKeyPermissionTargets("provider_account"),
    ).resolves.toHaveLength(2);
    expect(mockGet.mock.calls[1][1].params.page).toBe(2);
  });

  it("loads tracked deployments through authorized provider accounts", async () => {
    mockGet
      .mockResolvedValueOnce({
        data: { provider_accounts: [{ id: "provider-a" }], total: 1 },
      })
      .mockResolvedValueOnce({
        data: {
          deployments: [{ id: "deployment-a", display_name: "Deployment A" }],
          total: 1,
        },
      });
    await expect(getApiKeyPermissionTargets("deployment")).resolves.toEqual([
      { id: "deployment-a", name: "Deployment A" },
    ]);
    expect(mockGet.mock.calls[1][1].params.provider_id).toBe("provider-a");
  });

  it("loads sharing metadata without credential values", async () => {
    mockGet.mockResolvedValue({
      data: [{ id: "share-a", resource_id: "flow-a" }],
    });
    await expect(getApiKeyPermissionTargets("share")).resolves.toEqual([
      { id: "share-a", name: "flow-a" },
    ]);
  });
});
