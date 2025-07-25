import { useQuery } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import { api } from "../../api";

export interface InstallationStatus {
  installation_in_progress: boolean;
  last_result: {
    status: string;
    package_name: string;
    message: string;
  } | null;
}

async function getInstallationStatus(): Promise<InstallationStatus> {
  const response = await api.get(`${BASE_URL_API}packages/install/status`);
  return response.data;
}

export const useGetInstallationStatus = (enabled: boolean = true) => {
  return useQuery<InstallationStatus>({
    queryKey: ["installation-status"],
    queryFn: getInstallationStatus,
    enabled,
    refetchInterval: enabled ? 2000 : false, // Poll every 2 seconds when enabled
    refetchIntervalInBackground: false,
    retry: false,
  });
};
