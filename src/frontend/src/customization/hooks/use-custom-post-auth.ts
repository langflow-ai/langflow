import { UseRequestProcessor } from "@/controllers/API/services/request-processor";
import type { useQueryFunctionType } from "@/types/api";

export const useCustomPostAuth: useQueryFunctionType<undefined, null> = (
  options,
) => {
  const { query } = UseRequestProcessor();

  const getPostAuthFn = async () => {
    return null;
  };

  const queryResult = query(["usePostAuth"], getPostAuthFn, options);

  return queryResult;
};
