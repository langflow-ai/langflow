import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { IngestionRunInfo } from "./use-get-ingestion-runs";

export interface IngestionRunItemInfo {
  item_id: string;
  display_name: string;
  status: "succeeded" | "failed" | "skipped" | string;
  chunks_created: number;
  error_message: string | null;
}

export interface IngestionRunDetail extends IngestionRunInfo {
  source_config: Record<string, unknown>;
  items: IngestionRunItemInfo[];
}

interface GetIngestionRunParams {
  kb_name: string;
  run_id: string;
}

export const useGetIngestionRun: useQueryFunctionType<
  GetIngestionRunParams,
  IngestionRunDetail
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getRunFn = async (): Promise<IngestionRunDetail> => {
    const url = `${getURL("KNOWLEDGE_BASES")}/${params?.kb_name}/runs/${params?.run_id}`;
    const res = await api.get<IngestionRunDetail>(url);
    return res.data;
  };

  const queryResult: UseQueryResult<IngestionRunDetail, Error> = query(
    ["useGetIngestionRun", params?.kb_name, params?.run_id],
    getRunFn,
    {
      enabled: !!params?.kb_name && !!params?.run_id,
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
