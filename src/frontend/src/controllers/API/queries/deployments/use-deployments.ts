import type { UseMutationResult } from "@tanstack/react-query";
import buildQueryStringUrl from "@/controllers/utils/create-query-param-string";
import type {
  useMutationFunctionType,
  useQueryFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type DeploymentProvider = {
  id: string;
  account_id: string | null;
  provider_key: string;
  backend_url: string;
  registered_at: string | null;
};

export type DeploymentProviderCreatePayload = {
  account_id?: string;
  provider_key: string;
  backend_url: string;
  api_key: string;
};

export type DeploymentProviderUpdatePayload = {
  account_id?: string | null;
  provider_key?: string;
  backend_url?: string;
  api_key?: string;
};

export type DeploymentProvidersResponse = {
  providers: DeploymentProvider[];
  page: number;
  size: number;
  total: number;
};

export type DeploymentListItem = {
  id: string;
  resource_key?: string | null;
  type: string;
  name: string;
  attached_count?: number;
  description?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  provider_data?: {
    snapshot_ids?: string[];
    matched_history_ids?: string[];
    mode?: string;
    [key: string]: unknown;
  };
};

export type DeploymentListResponse = {
  deployments: DeploymentListItem[];
  deployment_type?: string | null;
  page: number;
  size: number;
  total: number;
};

export type DeploymentCreatePayload = {
  provider_id: string;
  spec: {
    name: string;
    description: string;
    type: "agent" | "mcp";
  };
  flow_versions?: {
    ids: string[];
  };
  config?: {
    reference_id?: string;
    raw_payload?: {
      name: string;
      description: string;
      environment_variables: Record<
        string,
        {
          source: "raw" | "variable";
          value: string;
        }
      >;
    };
  };
};

export type DeploymentCreateResponse = {
  id: string;
  config_id?: string | null;
  snapshot_ids?: string[];
  name?: string;
  description?: string;
  type?: string;
  provider_result?: Record<string, unknown>;
};

export type DeploymentExecutionPayload = {
  provider_id: string;
  deployment_id: string;
  deployment_type: "agent" | "mcp";
  input?: string | Record<string, unknown>;
  provider_input?: Record<string, unknown>;
};

export type DeploymentExecutionResponse = {
  execution_id?: string | null;
  deployment_id: string;
  deployment_type: "agent" | "mcp";
  status?: string | null;
  output?: string | Record<string, unknown> | null;
  provider_result?: Record<string, unknown> | null;
};

export type DetectDeploymentEnvVarsPayload = {
  reference_ids: string[];
};

export type DetectDeploymentEnvVarsResponse = {
  variables: Array<{
    key: string;
    global_variable_name?: string | null;
  }>;
};

type ProviderScopedParams = {
  providerId: string;
};

type PaginationParams = {
  page?: number;
  pageSize?: number;
  historyIds?: string[];
  matchLimit?: number;
};

export const useGetDeploymentProviders: useQueryFunctionType<
  undefined,
  DeploymentProvidersResponse,
  PaginationParams
> = (options) => {
  const { query } = UseRequestProcessor();

  const getProvidersFn = async (): Promise<DeploymentProvidersResponse> => {
    const page = options?.page ?? 1;
    const pageSize = options?.pageSize ?? 20;
    const { data } = await api.get<DeploymentProvidersResponse>(
      buildQueryStringUrl(`${getURL("DEPLOYMENTS")}/providers/`, {
        page,
        size: pageSize,
      }),
    );
    return data;
  };

  return query(
    ["useGetDeploymentProviders", options?.page ?? 1, options?.pageSize ?? 20],
    getProvidersFn,
    options,
  );
};

export const useGetDeployments: useQueryFunctionType<
  ProviderScopedParams & PaginationParams,
  DeploymentListResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getDeploymentsFn = async (): Promise<DeploymentListResponse> => {
    const queryParams = new URLSearchParams();
    queryParams.append("provider_id", params.providerId);
    queryParams.append("page", String(params.page ?? 1));
    queryParams.append("size", String(params.pageSize ?? 20));

    if (typeof params.matchLimit === "number") {
      queryParams.append("match_limit", String(params.matchLimit));
    }
    for (const historyId of params.historyIds ?? []) {
      const normalized = historyId.trim();
      if (normalized.length > 0) {
        queryParams.append("history_ids", normalized);
      }
    }

    const url = `${getURL("DEPLOYMENTS")}?${queryParams.toString()}`;
    const { data } = await api.get<DeploymentListResponse>(url);
    return data;
  };

  return query(
    [
      "useGetDeployments",
      params.providerId,
      params.page ?? 1,
      params.pageSize ?? 20,
      (params.historyIds ?? []).join(","),
      params.matchLimit ?? null,
    ],
    getDeploymentsFn,
    options,
  );
};

export const usePostCreateDeployment: useMutationFunctionType<
  undefined,
  DeploymentCreatePayload,
  DeploymentCreateResponse
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const createDeploymentFn = async (
    payload: DeploymentCreatePayload,
  ): Promise<DeploymentCreateResponse> => {
    const { data } = await api.post<DeploymentCreateResponse>(
      getURL("DEPLOYMENTS"),
      payload,
    );
    return data;
  };

  const mutation: UseMutationResult<
    DeploymentCreateResponse,
    Error,
    DeploymentCreatePayload
  > = mutate(["usePostCreateDeployment"], createDeploymentFn, {
    ...options,
  });

  return mutation;
};

export const usePostDetectDeploymentEnvVars: useMutationFunctionType<
  undefined,
  DetectDeploymentEnvVarsPayload,
  DetectDeploymentEnvVarsResponse
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const detectDeploymentEnvVarsFn = async (
    payload: DetectDeploymentEnvVarsPayload,
  ): Promise<DetectDeploymentEnvVarsResponse> => {
    const { data } = await api.post<DetectDeploymentEnvVarsResponse>(
      `${getURL("DEPLOYMENTS")}/variables/detections`,
      payload,
    );
    return data;
  };

  const mutation: UseMutationResult<
    DetectDeploymentEnvVarsResponse,
    Error,
    DetectDeploymentEnvVarsPayload
  > = mutate(["usePostDetectDeploymentEnvVars"], detectDeploymentEnvVarsFn, {
    ...options,
  });

  return mutation;
};

export const useGetDeploymentById: useMutationFunctionType<
  undefined,
  {
    deploymentId: string;
  },
  DeploymentListItem
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const getDeploymentByIdFn = async (payload: {
    deploymentId: string;
  }): Promise<DeploymentListItem> => {
    const { data } = await api.get<DeploymentListItem>(
      `${getURL("DEPLOYMENTS")}/${payload.deploymentId}`,
    );
    return data;
  };

  const mutation: UseMutationResult<
    DeploymentListItem,
    Error,
    {
      deploymentId: string;
    }
  > = mutate(["useGetDeploymentById"], getDeploymentByIdFn, {
    ...options,
  });

  return mutation;
};

export const usePostCreateDeploymentExecution: useMutationFunctionType<
  undefined,
  DeploymentExecutionPayload,
  DeploymentExecutionResponse
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const createDeploymentExecutionFn = async (
    payload: DeploymentExecutionPayload,
  ): Promise<DeploymentExecutionResponse> => {
    const { data } = await api.post<DeploymentExecutionResponse>(
      `${getURL("DEPLOYMENTS")}/executions`,
      payload,
    );
    return data;
  };

  const mutation: UseMutationResult<
    DeploymentExecutionResponse,
    Error,
    DeploymentExecutionPayload
  > = mutate(
    ["usePostCreateDeploymentExecution"],
    createDeploymentExecutionFn,
    {
      ...options,
    },
  );

  return mutation;
};

export const useGetDeploymentExecutionById: useMutationFunctionType<
  ProviderScopedParams,
  {
    executionId: string;
    deploymentId: string;
    deploymentType: "agent" | "mcp";
  },
  DeploymentExecutionResponse
> = (params, options) => {
  const { mutate } = UseRequestProcessor();

  const getDeploymentExecutionByIdFn = async (payload: {
    executionId: string;
    deploymentId: string;
    deploymentType: "agent" | "mcp";
  }): Promise<DeploymentExecutionResponse> => {
    const baseUrl = `${getURL("DEPLOYMENTS")}/executions/${payload.executionId}`;
    const url = buildQueryStringUrl(baseUrl, {
      provider_id: params.providerId,
      deployment_id: payload.deploymentId,
      deployment_type: payload.deploymentType,
    });
    const { data } = await api.get<DeploymentExecutionResponse>(url);
    return data;
  };

  const mutation: UseMutationResult<
    DeploymentExecutionResponse,
    Error,
    {
      executionId: string;
      deploymentId: string;
      deploymentType: "agent" | "mcp";
    }
  > = mutate(
    ["useGetDeploymentExecutionById", params.providerId],
    getDeploymentExecutionByIdFn,
    {
      ...options,
    },
  );

  return mutation;
};

export const usePostCreateDeploymentProvider: useMutationFunctionType<
  undefined,
  DeploymentProviderCreatePayload,
  DeploymentProvider
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const createProviderFn = async (
    payload: DeploymentProviderCreatePayload,
  ): Promise<DeploymentProvider> => {
    const cleanedPayload: DeploymentProviderCreatePayload = {
      ...payload,
      account_id: payload.account_id?.trim() || undefined,
    };
    const { data } = await api.post<DeploymentProvider>(
      `${getURL("DEPLOYMENTS")}/providers/`,
      cleanedPayload,
    );
    return data;
  };

  const mutation: UseMutationResult<
    DeploymentProvider,
    Error,
    DeploymentProviderCreatePayload
  > = mutate(["usePostCreateDeploymentProvider"], createProviderFn, {
    ...options,
  });

  return mutation;
};

export const usePatchUpdateDeploymentProvider: useMutationFunctionType<
  ProviderScopedParams,
  DeploymentProviderUpdatePayload,
  DeploymentProvider
> = (params, options) => {
  const { mutate } = UseRequestProcessor();

  const updateProviderFn = async (
    payload: DeploymentProviderUpdatePayload,
  ): Promise<DeploymentProvider> => {
    const cleanedPayload: DeploymentProviderUpdatePayload = {};

    if (payload.provider_key !== undefined) {
      cleanedPayload.provider_key = payload.provider_key.trim();
    }
    if (payload.backend_url !== undefined) {
      cleanedPayload.backend_url = payload.backend_url.trim();
    }
    if (payload.api_key !== undefined) {
      cleanedPayload.api_key = payload.api_key.trim();
    }
    if (payload.account_id !== undefined) {
      cleanedPayload.account_id =
        payload.account_id === null ? null : payload.account_id.trim();
    }

    const { data } = await api.patch<DeploymentProvider>(
      `${getURL("DEPLOYMENTS")}/providers/${params.providerId}`,
      cleanedPayload,
    );
    return data;
  };

  const mutation: UseMutationResult<
    DeploymentProvider,
    Error,
    DeploymentProviderUpdatePayload
  > = mutate(
    ["usePatchUpdateDeploymentProvider", params.providerId],
    updateProviderFn,
    {
      ...options,
    },
  );

  return mutation;
};

export const useDeleteDeploymentProvider: useMutationFunctionType<
  ProviderScopedParams,
  undefined,
  void
> = (params, options) => {
  const { mutate } = UseRequestProcessor();

  const deleteProviderFn = async (): Promise<void> => {
    await api.delete(`${getURL("DEPLOYMENTS")}/providers/${params.providerId}`);
  };

  const mutation: UseMutationResult<void, Error, undefined> = mutate(
    ["useDeleteDeploymentProvider", params.providerId],
    deleteProviderFn,
    {
      ...options,
    },
  );

  return mutation;
};
