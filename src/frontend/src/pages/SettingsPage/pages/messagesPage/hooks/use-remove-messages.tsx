import { deleteMessagesFn } from "../../../../../controllers/API";
import { useMessagesStore } from "../../../../../stores/messagesStore";

const useRemoveMessages = (
  setSelectedRows,
  setSuccessData,
  setErrorData,
  selectedRows,
) => {
  const deleteMessages = useMessagesStore((state) => state.removeMessages);

  const handleRemoveMessages = async () => {
    try {
      await deleteMessagesFn(selectedRows);
      deleteMessages(selectedRows);
      setSelectedRows([]);
      setSuccessData({
        title: "Messages deleted successfully.",
      });
    } catch (error) {
      setErrorData({
        title: "Error deleting messages.",
      });
    }
  };

  return { handleRemoveMessages };
};

export default useRemoveMessages;
