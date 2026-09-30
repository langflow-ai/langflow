/**
 * Tests for useGetEffectivePermissions.
 *
 * Mocks the request-processor and axios layers (mirroring the established
 * query-hook test pattern) so the hook can be invoked as a plain function and
 * its request shape asserted directly.
 */

const mockApiPost = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { post: (...args: unknown[]) => mockApiPost(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `api/v1/${key.toLowerCase()}`,
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    query: jest.fn(
      (
        _key: unknown,
        fn: () => Promise<unknown>,
        options?: { enabled?: boolean },
      ) => {
        // Honor the enabled flag so we can assert the query is skipped when
        // there are no resource ids to evaluate.
        if (options?.enabled !== false) {
          void fn();
        }
        return { data: undefined, isLoading: false, isError: false };
      },
    ),
  })),
}));

import { useGetEffectivePermissions } from "../use-get-effective-permissions";

const flushAsync = () => new Promise((resolve) => setTimeout(resolve, 10));

describe("useGetEffectivePermissions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiPost.mockResolvedValue({
      data: { resource_type: "flow", permissions: {} },
    });
  });

  it("POSTs the resource_type, resource_ids, actions and domain", async () => {
    useGetEffectivePermissions({
      resourceType: "flow",
      resourceIds: ["a", "b"],
      actions: ["read", "delete"],
      domain: "project:folder-1",
    });

    await flushAsync();

    expect(mockApiPost).toHaveBeenCalledTimes(1);
    expect(mockApiPost).toHaveBeenCalledWith("api/v1/authz_me_permissions", {
      resource_type: "flow",
      resource_ids: ["a", "b"],
      actions: ["read", "delete"],
      domain: "project:folder-1",
    });
  });

  it("omits actions and domain from the body when not provided", async () => {
    useGetEffectivePermissions({
      resourceType: "deployment",
      resourceIds: ["d1"],
    });

    await flushAsync();

    expect(mockApiPost).toHaveBeenCalledWith("api/v1/authz_me_permissions", {
      resource_type: "deployment",
      resource_ids: ["d1"],
    });
  });

  it("does not fire a request when there are no resource ids", async () => {
    useGetEffectivePermissions({ resourceType: "flow", resourceIds: [] });

    await flushAsync();

    expect(mockApiPost).not.toHaveBeenCalled();
  });

  it("caps resource_ids at 500 to match the backend limit", async () => {
    const ids = Array.from({ length: 600 }, (_, index) => `id-${index}`);
    useGetEffectivePermissions({ resourceType: "flow", resourceIds: ids });

    await flushAsync();

    expect(mockApiPost).toHaveBeenCalledTimes(1);
    const body = mockApiPost.mock.calls[0][1] as { resource_ids: string[] };
    expect(body.resource_ids).toHaveLength(500);
  });
});
