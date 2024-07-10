import {
  ERROR_UPDATING_COMPONENT,
  SAVE_DEBOUNCE_TIME,
  TITLE_ERROR_UPDATING_COMPONENT,
} from "@/constants/constants";
import { APITemplateType, ResponseErrorDetailAPI } from "@/types/api";
import { NodeDataType } from "@/types/flow";
import { UseMutationResult } from "@tanstack/react-query";
import { cloneDeep, debounce } from "lodash";
import pDebounce from "p-debounce";

export const mutateTemplate = debounce(
  async (
    newValue,
    data: NodeDataType,
    postTemplateValue: UseMutationResult<
      APITemplateType | undefined,
      ResponseErrorDetailAPI,
      any
    >,
    setNode,
    setErrorData,
  ) => {
    try {
      const newData = cloneDeep(data);
      const newTemplate = await postTemplateValue.mutateAsync({
        value: newValue,
      });
      if (newTemplate) {
        newData.node!.template = newTemplate;
      }
      setNode(data.id, (oldNode) => ({
        ...oldNode,
        data: newData,
      }));
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
