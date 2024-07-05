import { updateMessageApi } from "../../../../../controllers/API";
import { useMessagesStore } from "../../../../../stores/messagesStore";
import { Message } from "../../../../../types/messages";

const useUpdateMessage = (
  setSuccessData: (data: { title: string; list?: string[] }) => void,
  setErrorData: (data: { title: string; list?: string[] }) => void,
) => {
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
      return Promise.reject(error);
    }
  };

  return { handleUpdate };
};

export default useUpdateMessage;
