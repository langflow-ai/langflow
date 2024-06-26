import { cloneDeep } from "lodash";
import { useEffect } from "react";
import {
  ERROR_UPDATING_COMPONENT,
  TITLE_ERROR_UPDATING_COMPONENT,
} from "../../constants/constants";
import useAlertStore from "../../stores/alertStore";
import { ResponseErrorDetailAPI } from "../../types/api";
import { NodeDataType } from "../../types/flow";

const useFetchDataOnMount = (
  data: NodeDataType,
  name: string,
  handleUpdateValues: (name: string, data: NodeDataType) => Promise<any>,
  setNode: (id: string, callback: (oldNode: any) => any) => void,
  setIsLoading: (value: boolean) => void,
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
        setIsLoading(true);
        try {
          let newTemplate = await handleUpdateValues(name, data);

          if (newTemplate) {
            setNode(data.id, (oldNode) => {
              let newNode = cloneDeep(oldNode);
              newNode.data = {
                ...newNode.data,
              };
              newNode.data.node.template = newTemplate;
              return newNode;
            });
          }
        } catch (error) {
          let responseError = error as ResponseErrorDetailAPI;

          setErrorData({
            title: TITLE_ERROR_UPDATING_COMPONENT,
            list: [
              responseError?.response?.data?.detail ?? ERROR_UPDATING_COMPONENT,
            ],
          });
        }
        setIsLoading(false);
      }
    }
    fetchData();
  }, []); // Empty dependency array ensures that this effect runs only once, on mount
};

export default useFetchDataOnMount;
