import type { AxiosError } from "axios";
import type {
  useMutationFunctionType,
  useQueryFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import {
  type MaintenancePauseQueryOptions,
  migrationKeys,
  useMigrationPauseQuery,
} from "../migration";
import type {
  RepairOutcome,
  RepairPreview,
  ReportDetail,
  ReportHistory,
} from "./types";

export * from "./types";

export const useGetUpgradeReports: useQueryFunctionType<
  { offset: number },
  ReportHistory
> = (params, options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["useGetUpgradeReports", params],
    async () =>
      (
        await api.get(getURL("UPGRADE_REPORTS"), {
          params: { ...params, limit: 20 },
        })
      ).data,
    options,
  );
};
export const useGetUpgradeReport: useQueryFunctionType<
  { id: string },
  ReportDetail
> = ({ id }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["useGetUpgradeReport", id],
    async () => (await api.get(`${getURL("UPGRADE_REPORTS")}/${id}`)).data,
    { ...options, enabled: Boolean(id) && (options?.enabled ?? true) },
  );
};
export const useImportUpgradeReport: useMutationFunctionType<
  undefined,
  Blob,
  ReportDetail,
  AxiosError<{ detail?: { code?: string } }>
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["useImportUpgradeReport"],
    async (content: Blob) =>
      (
        await api.post(getURL("UPGRADE_REPORTS"), content, {
          headers: { "Content-Type": "application/json" },
        })
      ).data,
    {
      ...options,
      retry: false,
      onSettled: (...args) => {
        queryClient.invalidateQueries({ queryKey: ["useGetUpgradeReports"] });
        options?.onSettled?.(...args);
      },
    },
  );
};
export const useExportUpgradeReport: useMutationFunctionType<
  undefined,
  string,
  Blob,
  AxiosError
> = (options) => {
  const { mutate } = UseRequestProcessor();
  return mutate(
    ["useExportUpgradeReport"],
    async (id: string) =>
      (
        await api.get(`${getURL("UPGRADE_REPORTS")}/${id}/export`, {
          responseType: "blob",
        })
      ).data,
    { ...options, retry: false },
  );
};
export const useUpgradeMaintenance = (options?: MaintenancePauseQueryOptions) =>
  useMigrationPauseQuery(true, {
    refetchInterval: 5000,
    retry: false,
    ...options,
  });
export const usePreviewUpgradeRepair: useMutationFunctionType<
  undefined,
  { flow_ids: string[]; report_id: string },
  RepairPreview,
  AxiosError
> = (options) => {
  const { mutate } = UseRequestProcessor();
  return mutate(
    ["usePreviewUpgradeRepair"],
    async (body) =>
      (await api.post(getURL("UPGRADE_REPAIRS", { path: "preview" }), body))
        .data,
    { ...options, retry: false },
  );
};
export const useApplyUpgradeRepair: useMutationFunctionType<
  undefined,
  {
    flows: {
      flow_id: string;
      version_token: string | null;
      data_sha256: string;
    }[];
    target_sha256: string;
    report_id: string;
  },
  RepairPreview,
  AxiosError
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["useApplyUpgradeRepair"],
    async (body) =>
      (await api.post(getURL("UPGRADE_REPAIRS", { path: "apply" }), body)).data,
    {
      ...options,
      retry: false,
      onSettled: (...args) => {
        queryClient.invalidateQueries({
          queryKey: ["useGetUpgradeRepairOutcomes"],
        });
        queryClient.invalidateQueries({ queryKey: migrationKeys.pause });
        options?.onSettled?.(...args);
      },
    },
  );
};
export const useGetUpgradeRepairOutcomes: useQueryFunctionType<
  { id: string; offset?: number },
  { items: RepairOutcome[]; total: number }
> = ({ id, offset = 0 }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["useGetUpgradeRepairOutcomes", id, offset],
    async () =>
      (
        await api.get(`${getURL("UPGRADE_REPORTS")}/${id}/repairs`, {
          params: { offset, limit: 50 },
        })
      ).data,
    { ...options, enabled: Boolean(id) && (options?.enabled ?? true) },
  );
};
