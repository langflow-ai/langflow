import { useMemo } from "react";
import { LANGFLOW_SUPPORTED_TYPES } from "../../../constants/constants";
import { APIClassType } from "../../../types/api";
import { NodeDataType } from "../../../types/flow";

const useRowData = (
  myData: NodeDataType,
  nodeClass: APIClassType,
  open: boolean,
) => {
  const rowData = useMemo(() => {
    return Object.keys(myData.node!.template)
      .filter((key: string) => {
        const templateParam = myData.node!.template[key] as any;
        return (
          key.charAt(0) !== "_" &&
          templateParam.show &&
          !(
            (key === "code" && templateParam.type === "code") ||
            (key.includes("code") && templateParam.proxy)
          )
        );
      })
      .map((key: string) => {
        const templateParam = myData.node!.template[key] as any;
        return {
          ...templateParam,
          key: key,
          id: key,
        };
      });
  }, [open, nodeClass]);

  return rowData;
};

export default useRowData;
