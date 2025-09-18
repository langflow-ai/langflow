import { keepPreviousData } from "@tanstack/react-query";
import type { Message } from "@/types/messages";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface MessagesQueryParams {
  id?: string;
  session_id?: string;
  useLocalStorage?: boolean;
}

interface MessageResponse extends Omit<Message, "files"> {
  files: string;
}

export const useGetMessagesQuery: useQueryFunctionType<
  MessagesQueryParams,
  Message[]
> = ({ id, session_id, useLocalStorage }: MessagesQueryParams, options) => {
  const { query } = UseRequestProcessor();

  const getMessagesFn = async (): Promise<Message[]> => {
    const config: { params?: { flow_id?: string; session_id?: string } } = {};
    if (id) {
      config.params = { flow_id: id };
    }
    if (session_id) {
      config.params = { ...config.params, session_id };
    }

    if (!useLocalStorage) {
      const data = await api.get<MessageResponse[]>(
        `${getURL("MESSAGES")}`,
        config,
      );
      return data.data.map((message) => ({
        ...message,
        files: JSON.parse(message.files),
      }));
    } else {
      return JSON.parse(window.sessionStorage.getItem(id ?? "") || "[]");
    }
  };

  const queryResult = query(
    ["useGetMessagesQuery", { id, session_id }],
    getMessagesFn,
    {
      placeholderData: keepPreviousData,
      ...options,
    },
  );

  return queryResult;
};
