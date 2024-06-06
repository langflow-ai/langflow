const useSelectOptionsChange = (
  selectedFlowsComponentsCards,
  handleDuplicate,
  handleExport,
  setOpenDelete,
  setErrorDataState
) => {
  const handleSelectOptionsChange = (action) => {
    const hasSelected = selectedFlowsComponentsCards?.length > 0;
    if (!hasSelected) {
      setErrorDataState({
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
  };

  return { handleSelectOptionsChange };
};

export default useSelectOptionsChange;
