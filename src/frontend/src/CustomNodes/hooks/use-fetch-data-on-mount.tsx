import {
  APIClassType,
  APITemplateType,
  ResponseErrorDetailAPI,
} from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { useEffect } from "react";
import useAlertStore from "../../stores/alertStore";
import { mutateTemplate } from "../helpers/mutate-template";

const useFetchDataOnMount = (
  node: APIClassType,
  nodeId: string,
  name: string,
  postTemplateValue: UseMutationResult<
    APITemplateType | undefined,
    ResponseErrorDetailAPI,
    any
  >,
  setNode: (id: string, callback: (oldNode: any) => any) => void,
) => {
  const setErrorData = useAlertStore((state) => state.setErrorData);

  useEffect(() => {
    async function fetchData() {
      const template = node.template[name];
      if (
        (template?.real_time_refresh || template?.refresh_button) &&
        // options can be undefined but not an empty array
        (template?.options?.length ?? 0) === 0
      ) {
        mutateTemplate(
          template?.value,
          node,
          nodeId,
          postTemplateValue,
          setNode,
          setErrorData,
        );
      }
    }
    fetchData();
  }, []); // Empty dependency array ensures that this effect runs only once, on mount
};

export default useFetchDataOnMount;
