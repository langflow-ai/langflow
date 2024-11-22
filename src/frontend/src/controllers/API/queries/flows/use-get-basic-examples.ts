import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useQueryFunctionType } from "@/types/api";
import { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetBasicExamplesQuery: useQueryFunctionType<
  undefined,
  FlowType[]
> = (options) => {
  const { query } = UseRequestProcessor();
  const setExamples = useFlowsManagerStore((state) => state.setExamples);

  const getBasicExamplesFn = async () => {
    return await api.get<FlowType[]>(`${getURL("FLOWS")}/basic_examples/`);
  };

  const responseFn = async () => {
    const { data } = await getBasicExamplesFn();
    if (data) {
      setExamples(data);
    }
    return data;
  };

  const queryResult = query(["useGetBasicExamplesQuery"], responseFn, {
    ...options,
    retry: 3,
  });

  return queryResult;
};
