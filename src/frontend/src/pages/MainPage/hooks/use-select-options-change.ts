import { useCallback } from "react";
import { useTranslation } from "react-i18next";

const useSelectOptionsChange = (
  selectedFlowsComponentsCards: string[] | undefined,
  setErrorData: (data: { title: string; list: string[] }) => void,
  setOpenDelete: (value: boolean) => void,
  handleExport: () => void,
  handleDuplicate: () => void,
  handleEdit: () => void,
) => {
  const { t } = useTranslation();
  const handleSelectOptionsChange = useCallback(
    (action) => {
      const hasSelected = selectedFlowsComponentsCards?.length! > 0;
      if (!hasSelected) {
        setErrorData({
          title: t("errors.noItemsSelected"),
          list: [t("errors.selectItemsToDelete")],
        });
        return;
      }
      if (action === "delete") {
        setOpenDelete(true);
      } else if (action === "duplicate") {
        handleDuplicate();
      } else if (action === "export") {
        handleExport();
      } else if (action === "edit") {
        handleEdit();
      }
    },
    [
      selectedFlowsComponentsCards,
      setErrorData,
      setOpenDelete,
      handleDuplicate,
      handleEdit,
      handleExport,
    ],
  );

  return { handleSelectOptionsChange };
};

export default useSelectOptionsChange;
