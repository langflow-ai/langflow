import { deleteMessagesFn } from "../../../../../controllers/API";
import { useMessagesStore } from "../../../../../stores/messagesStore";
import { useTranslation } from "react-i18next";

const useRemoveMessages = (
  setSelectedRows: (data: string[]) => void,
  setSuccessData: (data: { title: string }) => void,
  setErrorData: (data: { title: string }) => void,
  selectedRows: string[],
) => {

  const { t } = useTranslation();

  const deleteMessages = useMessagesStore((state) => state.removeMessages);

  const handleRemoveMessages = async () => {
    try {
      await deleteMessagesFn(selectedRows);
      deleteMessages(selectedRows);
      setSelectedRows([]);
      setSuccessData({
        title: t("Messages deleted successfully."),
      });
    } catch (error) {
      setErrorData({
        title: t("Error deleting messages."),
      });
    }
  };

  return { handleRemoveMessages };
};

export default useRemoveMessages;
