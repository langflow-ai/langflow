import { useEffect } from "react";
import { getMessagesTable } from "../../../../../controllers/API";

const useMessagesTable = (setColumns, setRows, setMessages) => {
  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await getMessagesTable("union", undefined, ["index"]);
        const { columns, rows } = data;
        setColumns(columns.map((col) => ({ ...col, editable: true })));
        setRows(rows);
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
