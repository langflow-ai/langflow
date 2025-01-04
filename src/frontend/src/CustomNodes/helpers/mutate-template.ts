import {
  ERROR_UPDATING_COMPONENT,
  SAVE_DEBOUNCE_TIME,
  TITLE_ERROR_UPDATING_COMPONENT,
} from "@/constants/constants";
import { APIClassType, ResponseErrorDetailAPI } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { cloneDeep, debounce } from "lodash";

export const mutateTemplate = debounce(
  async (
    newValue,
    node: APIClassType,
    setNodeClass,
    postTemplateValue: UseMutationResult<
      APIClassType | undefined,
      ResponseErrorDetailAPI,
      any
    >,
    setErrorData,
    parameterName?: string,
    callback?: () => void,
  ) => {
    try {
      const newNode = cloneDeep(node);
      const newTemplate = await postTemplateValue.mutateAsync({
        value: newValue,
        field_name: parameterName,
      });
      if (newTemplate) {
        newNode.template = newTemplate.template;
        newNode.outputs = newTemplate.outputs;
      }
      setNodeClass(newNode);
      callback?.();
    } catch (e) {
      const error = e as ResponseErrorDetailAPI;
      setErrorData({
        title: TITLE_ERROR_UPDATING_COMPONENT,
        list: [error.response?.data?.detail || ERROR_UPDATING_COMPONENT],
      });
    }
  },
  SAVE_DEBOUNCE_TIME,
);
