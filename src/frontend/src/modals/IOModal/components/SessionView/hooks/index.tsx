import { deleteMessagesFn } from "../../../../../controllers/API";
import { useMessagesStore } from "../../../../../stores/messagesStore";
import { useTranslation } from "react-i18next";

const useRemoveSession = (setSuccessData, setErrorData) => {
  const { t } = useTranslation();
  const deleteSession = useMessagesStore((state) => state.deleteSession);
  const messages = useMessagesStore((state) => state.messages);

  const handleRemoveSession = async (session_id: string) => {
    try {
      await deleteMessagesFn(
        messages
          .filter((msg) => msg.session_id === session_id)
          .map((msg) => msg.id),
      );
      deleteSession(session_id);
      setSuccessData({
        title: t("Session deleted successfully."),
      });
    } catch (error) {
      setErrorData({
        title: t("Error deleting Session."),
      });
    }
  };

  return { handleRemoveSession };
};

export default useRemoveSession;
