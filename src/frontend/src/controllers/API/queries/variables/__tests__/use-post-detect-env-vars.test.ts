const mockApiPost = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { post: mockApiPost },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/variables"),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    // biome-ignore lint/suspicious/noExplicitAny: test mock
    mutate: jest.fn((_key: any, fn: any, options: any) => ({
      // biome-ignore lint/suspicious/noExplicitAny: test mock
      mutate: async (payload: any) => {
        const result = await fn(payload);
        options?.onSettled?.(result);
        return result;
      },
    })),
  })),
}));

import type {
  DetectEnvVarsPayload,
  DetectEnvVarsResponse,
} from "../use-post-detect-env-vars";
import { usePostDetectEnvVars } from "../use-post-detect-env-vars";

describe("usePostDetectEnvVars", () => {
  beforeEach(() => jest.clearAllMocks());

  it("posts to /variables/detections with flow_version_ids", async () => {
    const response: DetectEnvVarsResponse = { variables: [] };
    mockApiPost.mockResolvedValue({ data: response });

    const payload: DetectEnvVarsPayload = {
      flow_version_ids: ["fv-1", "fv-2"],
    };

    const mutation = usePostDetectEnvVars();
    await mutation.mutate(payload);

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/variables/detections",
      payload,
    );
  });

  it("returns detected variables with global_variable_name", async () => {
    const response: DetectEnvVarsResponse = {
      variables: [
        { key: "OPENAI_API_KEY", global_variable_name: "openai_key" },
        { key: "CUSTOM_VAR", global_variable_name: null },
      ],
    };
    mockApiPost.mockResolvedValue({ data: response });

    const mutation = usePostDetectEnvVars();
    const result = (await mutation.mutate({
      flow_version_ids: ["fv-1"],
    })) as unknown as DetectEnvVarsResponse;

    expect(result).toEqual(response);
    expect(result.variables).toHaveLength(2);
    expect(result.variables[0].global_variable_name).toBe("openai_key");
    expect(result.variables[1].global_variable_name).toBeNull();
  });

  it("returns empty variables array when no env vars detected", async () => {
    mockApiPost.mockResolvedValue({ data: { variables: [] } });

    const mutation = usePostDetectEnvVars();
    const result = (await mutation.mutate({
      flow_version_ids: ["fv-1"],
    })) as unknown as DetectEnvVarsResponse;

    expect(result.variables).toEqual([]);
  });
});
