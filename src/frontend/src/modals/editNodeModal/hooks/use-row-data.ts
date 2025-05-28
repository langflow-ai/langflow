import sortFields from "@/CustomNodes/utils/sort-fields";
import { useMemo } from "react";
import { APIClassType } from "../../../types/api";

const useRowData = (nodeClass: APIClassType, open: boolean) => {
  const rowData = useMemo(() => {
    return Object.keys(nodeClass.template)
      .filter((key: string) => {
        const templateParam = nodeClass.template[key] as any;
        return (
          key.charAt(0) !== "_" &&
          templateParam.show &&
          !(
            (key === "code" && templateParam.type === "code") ||
            (key.includes("code") && templateParam.proxy)
          )
        );
      })
      .sort((a, b) => sortFields(a, b, nodeClass.field_order ?? []))
      .map((key: string) => {
        const templateParam = nodeClass.template[key] as any;
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
