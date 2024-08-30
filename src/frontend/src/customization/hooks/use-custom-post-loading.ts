import { UseRequestProcessor } from "@/controllers/API/services/request-processor";
import { useQueryFunctionType } from "@/types/api";

export const useCustomPostLoading: useQueryFunctionType<undefined, null> = (
  options,
) => {
  const { query } = UseRequestProcessor();

  const getPostLoadingFn = async () => {
    return null;
  };

  const queryResult = query(["usePostLoading"], getPostLoadingFn, options);

  return queryResult;
};
