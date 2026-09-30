import type { Deployment } from "@/pages/MainPage/pages/deploymentsPage/types";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetDeploymentParams {
  deploymentId: string;
}

export const useGetDeployment: useQueryFunctionType<
  GetDeploymentParams,
  Deployment
> = ({ deploymentId }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<Deployment> => {
    const { data } = await api.get<Deployment>(
      `${getURL("DEPLOYMENTS")}/${deploymentId}`,
    );
    return data;
  };

  return query(["useGetDeployment", { deploymentId }], fn, options);
};
