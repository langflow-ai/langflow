import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { EvaluationInfo } from "./use-get-evaluations";

interface GetEvaluationParams {
  evaluationId: string;
}

export const useGetEvaluation: useQueryFunctionType<
  GetEvaluationParams,
  EvaluationInfo
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getEvaluationFn = async (): Promise<EvaluationInfo> => {
    const res = await api.get(
      `${getURL("EVALUATIONS")}/${params?.evaluationId}`,
    );
    return res.data;
  };

  const queryResult: UseQueryResult<EvaluationInfo, any> = query(
    ["useGetEvaluation", params?.evaluationId],
    getEvaluationFn,
    {
      enabled: !!params?.evaluationId,
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
