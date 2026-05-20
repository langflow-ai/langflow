import type { Trigger } from "@/pages/MainPage/pages/triggersPage/types";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetTriggersParams {
  flow_id?: string;
}

export const useGetTriggers: useQueryFunctionType<
  GetTriggersParams,
  Trigger[]
> = ({ flow_id } = {}, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<Trigger[]> => {
    const { data } = await api.get<Trigger[]>(`${getURL("TRIGGERS")}`, {
      params: flow_id ? { flow_id } : undefined,
    });
    return data;
  };

  return query(["useGetTriggers", { flow_id }], fn, options);
};
