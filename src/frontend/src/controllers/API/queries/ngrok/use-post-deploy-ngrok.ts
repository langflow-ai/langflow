import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useDeployNgrok: useMutationFunctionType<undefined, void> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();

  const deployNgrokFn = async (): Promise<void> => {
    const res = await api.post(`${getURL("DEPLOY")}/ngrok`);
    return res.data;
  };

  const mutation = mutate(["useDeployNgrok"], deployNgrokFn, {
    ...options,
  });

  return mutation;
};
