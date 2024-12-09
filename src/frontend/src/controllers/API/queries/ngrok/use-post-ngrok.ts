import { AddFolderType } from "@/pages/MainPage/entities";
import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostDeployNgrok {}

export const useDeployNgrok: useMutationFunctionType<undefined, void> = (
  options?,
) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deployNgrokFn = async (): Promise<void> => {
    const res = await api.post(`${getURL("DEPLOY")}`);
    return res.data;
  };

  const mutation = mutate(["useDeployNgrok"], deployNgrokFn, {
    ...options,
    onSuccess: () => {
      return queryClient.refetchQueries({ queryKey: ["useDeployNgrok"] });
    },
  });

  return mutation;
};
