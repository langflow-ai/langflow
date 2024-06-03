import { useMessagesStore } from "../../../../../stores/messagesStore";
import { Message } from "../../../../../types/messages";
import { updateMessageApi } from "../../../../../controllers/API";

const useUpdateMessage = (setSuccessData, setErrorData) => {
  const updateMessage = useMessagesStore((state) => state.updateMessage);

  const handleUpdate = async (data: Message) => {
    try {
      await updateMessageApi(data);

      updateMessage(data);

      // Set success message
      setSuccessData({
        title: "Messages updated successfully.",
      });
    } catch (error) {
      // Set error message
      setErrorData({
        title: "Error updating messages.",
      });
    }
  };

  return { handleUpdate };
};

export default useUpdateMessage;
