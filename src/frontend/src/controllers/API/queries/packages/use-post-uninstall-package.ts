import { useMutation } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { BASE_URL_API } from "@/constants/constants";
import { api } from "../../api";

export interface UninstallPackageRequest {
  package_name: string;
}

export interface UninstallPackageResponse {
  message: string;
  package_name: string;
  status: string;
}

async function uninstallPackageRequest(
  packageName: string,
): Promise<UninstallPackageResponse> {
  const response = await api.post(`${BASE_URL_API}packages/uninstall`, {
    package_name: packageName,
  });
  return response.data;
}

export const useUninstallPackage = () => {
  return useMutation<UninstallPackageResponse, AxiosError, string>({
    mutationFn: uninstallPackageRequest,
  });
};
