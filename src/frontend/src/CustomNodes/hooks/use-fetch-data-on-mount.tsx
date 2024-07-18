import { APITemplateType, ResponseErrorDetailAPI } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { useEffect } from "react";
import useAlertStore from "../../stores/alertStore";
import { NodeDataType } from "../../types/flow";
import { mutateTemplate } from "../helpers/mutate-template";

const useFetchDataOnMount = (
  data: NodeDataType,
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
      if (
        (data.node?.template[name]?.real_time_refresh ||
          data.node?.template[name]?.refresh_button) &&
        // options can be undefined but not an empty array
        (data.node?.template[name]?.options?.length ?? 0) === 0
      ) {
        mutateTemplate(
          data.node?.template[name]?.value,
          data,
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
