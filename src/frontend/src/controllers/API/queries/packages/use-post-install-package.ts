import { useMutation } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { BASE_URL_API } from "@/constants/constants";
import { api } from "../../api";

export interface InstallPackageRequest {
  package_name: string;
}

export interface InstallPackageResponse {
  message: string;
  package_name: string;
  status: string;
}

async function installPackageRequest(
  packageName: string,
): Promise<InstallPackageResponse> {
  const response = await api.post(`${BASE_URL_API}packages/install`, {
    package_name: packageName,
  });
  return response.data;
}

export const useInstallPackage = () => {
  return useMutation<InstallPackageResponse, AxiosError, string>({
    mutationFn: installPackageRequest,
  });
};
