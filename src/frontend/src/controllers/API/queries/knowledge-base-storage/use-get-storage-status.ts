import useAuthStore from "@/stores/authStore";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface StorageUpgrade {
  kb_id: string;
  name: string;
  storage_state: string;
  migration_id: string | null;
  phase: string;
  error_code: string | null;
  can_retry: boolean;
}

export interface StorageUpgradeStatus {
  stores: StorageUpgrade[];
  inventory: { complete: boolean; issues: number } | null;
  is_admin: boolean;
  running: boolean;
  revision: string;
}

export const useGetStorageStatus: useQueryFunctionType<
  undefined,
  StorageUpgradeStatus
> = (options?) => {
  const { query } = UseRequestProcessor();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  return query(
    ["useGetStorageStatus"],
    async (): Promise<StorageUpgradeStatus> => {
      const response = await api.get<StorageUpgradeStatus>(
        `${getURL("KNOWLEDGE_BASE_STORAGE")}/status`,
      );
      return response.data;
    },
    {
      refetchInterval: (query) =>
        (query.state.data as StorageUpgradeStatus | undefined)?.running
          ? 2000
          : 30000,
      refetchOnWindowFocus: true,
      ...options,
      enabled: isAuthenticated && (options?.enabled ?? true),
    },
  );
};
