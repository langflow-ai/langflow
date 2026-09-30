const mockApiPost = jest.fn();

type MutationOptions<TData, TVariables> = {
  onSuccess?: (data: TData, variables: TVariables, context: undefined) => void;
  onError?: (error: Error, variables: TVariables, context: undefined) => void;
};

type MutationFn<TVariables, TData> = (payload: TVariables) => Promise<TData>;

jest.mock("@/controllers/API/api", () => ({
  api: { post: mockApiPost },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/extensions"),
}));

jest.mock("@/controllers/API/helpers/extract-api-error-message", () => ({
  extractApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: jest.fn(
      <TVariables, TData>(
        _key: unknown,
        fn: MutationFn<TVariables, TData>,
        options: MutationOptions<TData, TVariables>,
      ) => ({
        // Resolve / reject the promise so each test can branch on
        // success vs error without actually wiring react-query.
        mutate: async (payload: TVariables) => {
          try {
            const result = await fn(payload);
            options?.onSuccess?.(result, payload, undefined);
            return result;
          } catch (err) {
            options?.onError?.(err as Error, payload, undefined);
            throw err;
          }
        },
      }),
    ),
    queryClient: {},
  })),
}));

import { useReloadBundle } from "../use-reload-bundle";

describe("useReloadBundle", () => {
  beforeEach(() => {
    mockApiPost.mockReset();
  });

  it("posts to /extensions/{id}/bundles/{name}/reload and returns the body", async () => {
    const body = {
      ok: true,
      bundle: "openai",
      reload_id: "abc",
      components_added: ["Foo"],
      components_removed: [],
      components_changed: [],
      errors: [],
      warnings: [],
    };
    mockApiPost.mockResolvedValue({ data: body });

    const onSuccess = jest.fn();
    const mutation = useReloadBundle({ onSuccess });
    await mutation.mutate({ extensionId: "lfx-openai", bundleName: "openai" });

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/extensions/lfx-openai/bundles/openai/reload",
    );
    expect(onSuccess).toHaveBeenCalledWith(body, expect.anything(), undefined);
  });

  it("rethrows reload-in-progress with a parseable shape", async () => {
    mockApiPost.mockRejectedValue({
      response: {
        data: {
          detail: {
            code: "reload-in-progress",
            message: "already running",
            bundle: "openai",
          },
        },
      },
    });

    const onError = jest.fn();
    const mutation = useReloadBundle({ onError });
    await expect(
      mutation.mutate({ extensionId: "lfx-openai", bundleName: "openai" }),
    ).rejects.toThrow(/^reload-in-progress: already running$/);
    expect(onError).toHaveBeenCalled();
  });

  it("unwraps a 422 typed structural failure into the ReloadResult body", async () => {
    const result = {
      ok: false,
      bundle: "openai",
      reload_id: "abc",
      components_added: [],
      components_removed: [],
      components_changed: [],
      errors: [
        {
          code: "module-import-failed",
          message: "could not import openai_chat",
          hint: "fix the syntax error",
          location: "openai/openai_chat.py",
          content: null,
          ref_url: null,
        },
      ],
      warnings: [],
    };
    mockApiPost.mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail: {
            code: "module-import-failed",
            message: "could not import openai_chat",
            result,
          },
        },
      },
    });

    const onSuccess = jest.fn();
    const onError = jest.fn();
    const mutation = useReloadBundle({ onSuccess, onError });
    await mutation.mutate({ extensionId: "lfx-openai", bundleName: "openai" });

    expect(onSuccess).toHaveBeenCalledWith(
      result,
      expect.anything(),
      undefined,
    );
    expect(onError).not.toHaveBeenCalled();
  });

  it("falls back to extractApiErrorMessage for arbitrary failures", async () => {
    mockApiPost.mockRejectedValue(new Error("boom"));

    const onError = jest.fn();
    const mutation = useReloadBundle({ onError });
    await expect(
      mutation.mutate({ extensionId: "lfx-openai", bundleName: "openai" }),
    ).rejects.toThrow("Failed to reload bundle");
    expect(onError).toHaveBeenCalled();
  });
});
