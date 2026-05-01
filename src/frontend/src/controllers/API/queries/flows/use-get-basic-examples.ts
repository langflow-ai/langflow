import { useTranslation } from "react-i18next";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { useQueryFunctionType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetBasicExamplesQuery: useQueryFunctionType<
  undefined,
  FlowType[]
> = (options) => {
  const { query } = UseRequestProcessor();
  const setExamples = useFlowsManagerStore((state) => state.setExamples);
  const { i18n } = useTranslation();

  const responseFn = async () => {
    const { data } = await api.get<FlowType[]>(
      `${getURL("FLOWS")}/basic_examples/`,
    );
    if (data) {
      setExamples(data);
    }
    return data;
  };

  return query(["useGetBasicExamplesQuery", i18n.language], responseFn, {
    ...options,
    retry: 3,
  });
};
