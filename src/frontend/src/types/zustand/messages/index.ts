import { Message } from "../../messages";

export type MessagesStoreType = {
  messages: Message[];
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  removeMessage: (message: Message) => void;
  updateMessage: (message: Message) => void;
  clearMessages: () => void;
  removeMessages: (ids: number[]) => void;
};
