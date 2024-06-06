import { useMemo } from "react";
import { LANGFLOW_SUPPORTED_TYPES } from "../../../constants/constants";
import { TemplateVariableType } from "../../../types/api";

const useRowData = (myData, open) => {
  const rowData = useMemo(() => {
    return Object.keys(myData.node!.template)
      .filter((key: string) => {
        const templateParam = myData.node!.template[
          key
        ] as TemplateVariableType;
        return (
          key.charAt(0) !== "_" &&
          templateParam.show &&
          LANGFLOW_SUPPORTED_TYPES.has(templateParam.type) &&
          !(
            (key === "code" && templateParam.type === "code") ||
            (key.includes("code") && templateParam.proxy)
          )
        );
      })
      .map((key: string) => {
        const templateParam = myData.node!.template[
          key
        ] as TemplateVariableType;
        return {
          ...templateParam,
          key: key,
          id: key,
        };
      });
  }, [open, myData]);

  return rowData;
};

export default useRowData;
