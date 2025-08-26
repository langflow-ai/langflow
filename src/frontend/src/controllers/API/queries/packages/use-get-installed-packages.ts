import { useQuery } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import { api } from "../../api";

export interface InstalledPackage {
  name: string;
  version: string;
}

async function getInstalledPackages(): Promise<InstalledPackage[]> {
  const response = await api.get(`${BASE_URL_API}packages/installed`);
  return response.data;
}

export const useGetInstalledPackages = () => {
  return useQuery<InstalledPackage[]>({
    queryKey: ["installed-packages"],
    queryFn: getInstalledPackages,
    staleTime: 30000, // Consider data fresh for 30 seconds
    retry: 2,
  });
};
