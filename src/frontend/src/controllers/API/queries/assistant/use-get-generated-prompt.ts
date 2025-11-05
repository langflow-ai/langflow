import { keepPreviousData } from "@tanstack/react-query";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetGeneratedPromptQuery: useQueryFunctionType<any, any> = (
  { compId, flowId, fieldName },
  options,
) => {
  const { query } = UseRequestProcessor();

  const getGeneratedPromptFn = async (compId, flowId, fieldName) => {
    return await api.post<any>(
      getURL("RUN_SESSION", {
        // assistantFlowId: "69aa447b-997e-4efd-bc33-909694cf9f02",
        assistantFlowId: "SystemMessageGen",
      }),
      {
        input_value: "",
        input_type: "chat",
        output_type: "text",
      },
      {
        headers: {
          "X-Langflow-Global-Var-COMPONENT_ID": compId,
          "X-Langflow-Global-Var-FLOW_ID": flowId,
          "X-Langflow-Global-Var-FIELD_NAME": fieldName,
        },
      },
    );
  };

  const responseFn = async () => {
    const data = await getGeneratedPromptFn(compId, flowId, fieldName);
    return data;
  };

  const queryResult = query(
    ["useGetGeneratedPromptQuery", { compId, flowId, fieldName }],
    responseFn,
    {
      enabled: false,
      retry: false,
      placeholderData: keepPreviousData,
      ...options,
    },
  );

  return queryResult;
};
