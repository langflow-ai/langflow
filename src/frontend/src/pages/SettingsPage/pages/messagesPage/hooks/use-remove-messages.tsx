import { deleteMessagesFn } from "../../../../../controllers/API";
import { useMessagesStore } from "../../../../../stores/messagesStore";

const useRemoveMessages = (
  setRows,
  setSelectedRows,
  setSuccessData,
  setErrorData,
  selectedRows,
) => {
  const deleteMessages = useMessagesStore((state) => state.removeMessages);

  const handleRemoveMessages = async () => {
    try {
      // Call the deleteMessagesFn to perform the deletion
      await deleteMessagesFn(selectedRows);

      // Assuming deleteMessages is a separate function that updates state after deletion
      const res = await deleteMessages(selectedRows);
      setRows(res);

      // Clear the selected rows
      setSelectedRows([]);

      // Set success message
      setSuccessData({
        title: "Messages deleted successfully.",
      });
    } catch (error) {
      // Set error message
      setErrorData({
        title: "Error deleting messages.",
      });
    }
  };

  return { handleRemoveMessages };
};

export default useRemoveMessages;
