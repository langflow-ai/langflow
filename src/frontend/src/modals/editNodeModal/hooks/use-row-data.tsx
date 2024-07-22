import sortFields from "@/CustomNodes/utils/sort-fields";
import { useMemo } from "react";
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
      .sort((a, b) => sortFields(a, b, myData.node?.field_order ?? []))
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
