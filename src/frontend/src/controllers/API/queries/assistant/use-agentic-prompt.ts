import { keepPreviousData } from "@tanstack/react-query";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useAgenticPromptQuery: useQueryFunctionType<
  { compId; flowId; fieldName; inputValue },
  {}
> = ({ compId, flowId, fieldName, inputValue }, options) => {
  const { query } = UseRequestProcessor();

  const getAgenticPromptFn = async (compId, flowId, fieldName, inputValue) => {
    return await api.post(
      getURL("AGENTIC_PROMPT"),
      {
        flow_id: flowId,
        component_id: compId,
        field_name: fieldName,
        input_value: inputValue,
      },
      {
        headers: {},
      },
    );
  };

  const responseFn = async () => {
    return await getAgenticPromptFn(compId, flowId, fieldName, inputValue);
  };

  const queryResult = query(
    ["useAgenticPromptQuery", { compId, flowId, fieldName, inputValue }],
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
