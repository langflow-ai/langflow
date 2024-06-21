import { deleteMessagesFn } from "../../../../../controllers/API";
import { useMessagesStore } from "../../../../../stores/messagesStore";

const useRemoveSession = (setSuccessData, setErrorData) => {
  const deleteSession = useMessagesStore((state) => state.deleteSession);
  const messages = useMessagesStore((state) => state.messages);

  const handleRemoveSession = async (session_id: string) => {
    try {
      await deleteMessagesFn(
        messages
          .filter((msg) => msg.session_id === session_id)
          .map((msg) => msg.index),
      );
      deleteSession(session_id);
      setSuccessData({
        title: "Session deleted successfully.",
      });
    } catch (error) {
      setErrorData({
        title: "Error deleting Session.",
      });
    }
  };

  return { handleRemoveSession };
};

export default useRemoveSession;
