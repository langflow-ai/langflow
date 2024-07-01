import { useCallback } from "react";

const useSelectOptionsChange = (
  selectedFlowsComponentsCards: string[] | undefined,
  setErrorData: (data: { title: string; list: string[] }) => void,
  setOpenDelete: (value: boolean) => void,
  handleDuplicate: () => void,
  handleExport: () => void,
) => {
  const handleSelectOptionsChange = useCallback(
    (action) => {
      const hasSelected = selectedFlowsComponentsCards?.length! > 0;
      if (!hasSelected) {
        setErrorData({
          title: "No items selected",
          list: ["Please select items to delete"],
        });
        return;
      }
      if (action === "delete") {
        setOpenDelete(true);
      } else if (action === "duplicate") {
        handleDuplicate();
      } else if (action === "export") {
        handleExport();
      }
    },
    [
      selectedFlowsComponentsCards,
      setErrorData,
      setOpenDelete,
      handleDuplicate,
      handleExport,
    ],
  );

  return { handleSelectOptionsChange };
};

export default useSelectOptionsChange;
