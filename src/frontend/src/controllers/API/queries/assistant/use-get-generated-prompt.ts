import { keepPreviousData } from "@tanstack/react-query";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetGeneratedPromptQuery: useQueryFunctionType<any, any> = (
  { compId, flowId, fieldName },
  options,
) => {
  const { query } = UseRequestProcessor();

  const getGeneratedPromptFn = async (compId, flowId, fieldName) => {
    return await api.post<any>(
      "api/v1/responses",
      {
        model: "19287914-c1cc-436f-a23e-e916cf65d23c",
        input: "generate a valid input for this field",
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
      placeholderData: keepPreviousData,
      ...options,
    },
  );

  return queryResult;
};
