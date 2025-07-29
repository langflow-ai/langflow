import { UseRequestProcessor } from "@/controllers/API/services/request-processor";
import type { useQueryFunctionType } from "@/types/api";

export const useCustomPrimaryLoading: useQueryFunctionType<undefined, null> = (
  options,
) => {
  const { query } = UseRequestProcessor();

  const getPrimaryLoadingFn = async () => {
    return null;
  };

  const queryResult = query(
    ["usePrimaryLoading"],
    getPrimaryLoadingFn,
    options,
  );

  return queryResult;
};
