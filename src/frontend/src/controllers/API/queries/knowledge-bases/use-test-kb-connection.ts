import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface TestBackendConnectionRequest {
  backend_type: string;
  backend_config?: Record<string, unknown>;
}

export interface TestBackendConnectionResponse {
  ok: boolean;
  message: string;
  details?: Record<string, unknown>;
}

export const useTestKnowledgeBackendConnection: useMutationFunctionType<
  undefined,
  TestBackendConnectionRequest,
  TestBackendConnectionResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const testBackendConnectionFn = async (
    payload: TestBackendConnectionRequest,
  ): Promise<TestBackendConnectionResponse> => {
    const res = await api.post<TestBackendConnectionResponse>(
      `${getURL("KNOWLEDGE_BASES")}/test-connection`,
      payload,
    );
    return res.data;
  };

  const mutation: UseMutationResult<
    TestBackendConnectionResponse,
    Error,
    TestBackendConnectionRequest
  > = mutate(
    ["useTestKnowledgeBackendConnection"],
    testBackendConnectionFn,
    {
      ...options,
    },
  );

  return mutation;
};
