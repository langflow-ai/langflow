import type { APIClassType, ResponseErrorDetailAPI } from "@/types/api";
import type { UseMutationResult } from "@tanstack/react-query";
import { useEffect } from "react";
import useAlertStore from "../../stores/alertStore";
import { mutateTemplate } from "../helpers/mutate-template";

const useFetchDataOnMount = (
  node: APIClassType,
  nodeId: string,
  setNodeClass: (node: APIClassType) => void,
  name: string,
  postTemplateValue: UseMutationResult<
    APIClassType | undefined,
    ResponseErrorDetailAPI,
    any
  >,
) => {
  const setErrorData = useAlertStore((state) => state.setErrorData);

  useEffect(() => {
    async function fetchData() {
      const template = node.template[name];
      if (
        (template?.real_time_refresh ||
          template?.refresh_button ||
          (node.tool_mode && name === "tools_metadata")) &&
        // options can be undefined but not an empty array
        (template?.options?.length ?? 0) === 0
      ) {
        mutateTemplate(
          template?.value,
          nodeId,
          node,
          setNodeClass,
          postTemplateValue,
          setErrorData,
          name,
          () => {},
          node.tool_mode,
        );
      }
    }
    fetchData();
  }, []); // Empty dependency array ensures that this effect runs only once, on mount
};

export default useFetchDataOnMount;
