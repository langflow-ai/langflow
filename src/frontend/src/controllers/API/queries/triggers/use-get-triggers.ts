import type { TriggerInstance } from "@/pages/MainPage/pages/triggersPage/types";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetTriggers: useQueryFunctionType<
  undefined,
  TriggerInstance[]
> = (options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<TriggerInstance[]> => {
    const { data } = await api.get<TriggerInstance[]>(`${getURL("TRIGGERS")}`);
    return data;
  };

  return query(["useGetTriggers"], fn, options);
};
