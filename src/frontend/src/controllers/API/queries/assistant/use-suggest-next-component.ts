import { keepPreviousData } from "@tanstack/react-query";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetNextSuggestedComponentQuery: useQueryFunctionType<
  { compId; flowId; fieldName; inputValue },
  {}
> = ({ compId, flowId, fieldName, inputValue }, options) => {
  const { query } = UseRequestProcessor();

  const getNextSuggestedComponentFn = async (
    compId,
    flowId,
    fieldName,
    inputValue,
  ) => {
    return await api.post(
      getURL("RUN_SESSION", {
        assistantFlowId: "SuggestNextComponent",
      }),
      {
        input_value: inputValue || "",
        input_type: "chat",
        output_type: "chat",
        stream: true,
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
    return await getNextSuggestedComponentFn(
      compId,
      flowId,
      fieldName,
      inputValue,
    );
  };

  const queryResult = query(
    [
      "useGetNextSuggestedComponentQuery",
      { compId, flowId, fieldName, inputValue },
    ],
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
