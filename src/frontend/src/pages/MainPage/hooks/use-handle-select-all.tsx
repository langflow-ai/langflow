import { useCallback } from "react";
import { FlowType } from "../../../types/flow";

const useSelectAll = (
  flowsFromFolder: FlowType[],
  getValues: () => Record<string, boolean>,
  setValue: (key: string, value: boolean) => void,
) => {
  const handleSelectAll = useCallback(
    (select) => {
      const flowsFromFolderIds = flowsFromFolder?.map((f) => f.id);
      if (select) {
        Object.keys(getValues()).forEach((key) => {
          if (!flowsFromFolderIds?.includes(key)) return;
          setValue(key, true);
        });
        return;
      }

      Object.keys(getValues()).forEach((key) => {
        setValue(key, false);
      });
    },
    [flowsFromFolder, getValues, setValue],
  );

  return { handleSelectAll };
};

export default useSelectAll;
