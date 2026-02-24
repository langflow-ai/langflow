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
  updated_at: string | null;
  has_api_key: boolean;
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
  deployment_providers: DeploymentProvider[];
};

export type DeploymentListItem = {
  id: string;
  type: string;
  name: string;
  created_at?: string | null;
  updated_at?: string | null;
  provider_data?: {
    snapshot_ids?: string[];
    mode?: string;
    [key: string]: unknown;
  };
};

export type DeploymentListResponse = {
  deployments: DeploymentListItem[];
  deployment_type?: string | null;
};

export type DeploymentConfigItem = {
  id: string;
  name: string;
  description?: string | null;
  provider_data?: {
    [key: string]: unknown;
  };
};

export type DeploymentConfigsResponse = {
  configs: DeploymentConfigItem[];
};

export type DeploymentSnapshotItem = {
  id: string;
  name: string;
  description?: string | null;
  provider_data?: {
    langflow_id?: string;
    project_id?: string;
    [key: string]: unknown;
  };
};

export type DeploymentSnapshotsResponse = {
  snapshots: DeploymentSnapshotItem[];
  artifact_type: string;
};

export type DeploymentCreatePayload = {
  spec: {
    name: string;
    description: string;
    type: "agent" | "mcp";
  };
  snapshot?: {
    artifact_type: "flow";
    reference_ids?: string[];
    raw_payloads?: Record<string, unknown>[];
  };
  config?: {
    reference_id?: string;
    raw_payload?: {
      name: string;
      description: string;
      environment_variables: Record<
        string,
        {
          source: "raw";
          value: string;
        }
      >;
    };
  };
};

export type DeploymentCreateResponse = {
  id: string;
  name?: string;
  description?: string;
  type?: string;
  provider_result?: Record<string, unknown>;
};

type ProviderScopedParams = {
  providerId: string;
};

const addProviderId = (url: string, providerId: string): string =>
  buildQueryStringUrl(url, { provider_id: providerId });

export const useGetDeploymentProviders: useQueryFunctionType<
  undefined,
  DeploymentProvidersResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getProvidersFn = async (): Promise<DeploymentProvidersResponse> => {
    const { data } = await api.get<DeploymentProvidersResponse>(
      `${getURL("DEPLOYMENTS")}/providers/`,
    );
    return data;
  };

  return query(["useGetDeploymentProviders"], getProvidersFn, options);
};

export const useGetDeployments: useQueryFunctionType<
  ProviderScopedParams,
  DeploymentListResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getDeploymentsFn = async (): Promise<DeploymentListResponse> => {
    const url = addProviderId(getURL("DEPLOYMENTS"), params.providerId);
    const { data } = await api.get<DeploymentListResponse>(url);
    return data;
  };

  return query(
    ["useGetDeployments", params.providerId],
    getDeploymentsFn,
    options,
  );
};

export const useGetDeploymentConfigs: useQueryFunctionType<
  ProviderScopedParams,
  DeploymentConfigsResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getConfigsFn = async (): Promise<DeploymentConfigsResponse> => {
    const url = addProviderId(
      `${getURL("DEPLOYMENTS")}/configs`,
      params.providerId,
    );
    const { data } = await api.get<DeploymentConfigsResponse>(url);
    return data;
  };

  return query(
    ["useGetDeploymentConfigs", params.providerId],
    getConfigsFn,
    options,
  );
};

export const useGetDeploymentSnapshots: useQueryFunctionType<
  ProviderScopedParams,
  DeploymentSnapshotsResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getSnapshotsFn = async (): Promise<DeploymentSnapshotsResponse> => {
    const url = addProviderId(
      `${getURL("DEPLOYMENTS")}/snapshots`,
      params.providerId,
    );
    const { data } = await api.get<DeploymentSnapshotsResponse>(url);
    return data;
  };

  return query(
    ["useGetDeploymentSnapshots", params.providerId],
    getSnapshotsFn,
    options,
  );
};

export const usePostCreateDeployment: useMutationFunctionType<
  ProviderScopedParams,
  DeploymentCreatePayload,
  DeploymentCreateResponse
> = (params, options) => {
  const { mutate } = UseRequestProcessor();

  const createDeploymentFn = async (
    payload: DeploymentCreatePayload,
  ): Promise<DeploymentCreateResponse> => {
    const url = addProviderId(getURL("DEPLOYMENTS"), params.providerId);
    const { data } = await api.post<DeploymentCreateResponse>(url, payload);
    return data;
  };

  const mutation: UseMutationResult<
    DeploymentCreateResponse,
    Error,
    DeploymentCreatePayload
  > = mutate(
    ["usePostCreateDeployment", params.providerId],
    createDeploymentFn,
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
