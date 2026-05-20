import type { Trigger } from "@/pages/MainPage/pages/triggersPage/types";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetTriggerParams {
  triggerId: string;
}

export const useGetTrigger: useQueryFunctionType<
  GetTriggerParams,
  Trigger
> = ({ triggerId }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<Trigger> => {
    const { data } = await api.get<Trigger>(
      `${getURL("TRIGGERS")}/${triggerId}`,
    );
    return data;
  };

  return query(["useGetTrigger", { triggerId }], fn, options);
};
