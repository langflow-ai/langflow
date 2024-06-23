import { useCallback } from "react";

const useSelectOptionsChange = (
  selectedFlowsComponentsCards,
  setErrorData,
  setOpenDelete,
  handleDuplicate,
  handleExport,
) => {
  const handleSelectOptionsChange = useCallback(
    (action) => {
      const hasSelected = selectedFlowsComponentsCards?.length > 0;
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
