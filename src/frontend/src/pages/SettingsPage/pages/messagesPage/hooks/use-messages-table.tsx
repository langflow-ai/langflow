import { useEffect } from "react";
import { getMessagesTable } from "../../../../../controllers/API";
import { useMessagesStore } from "../../../../../stores/messagesStore";

const useMessagesTable = (setColumns) => {
  const setMessages = useMessagesStore((state) => state.setMessages);
  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await getMessagesTable("union", undefined, ["index"]);
        const { columns, rows } = data;
        setColumns(columns);
        setMessages(rows);
      } catch (error) {
        console.error("Error fetching messages:", error);
      }
    };
    fetchData();
  }, []);

  return null;
};

export default useMessagesTable;
