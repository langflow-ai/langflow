import { Message } from "../../messages";

export type MessagePatch = {
  op: "replace" | "add" | "remove";
  path: string;
  value: any;
}[];

export interface MessagesStoreType {
  messages: Message[];
  setMessages: (messages: Message[]) => void;
  addMessage: (message: Message) => void;
  removeMessage: (message: Message) => void;
  updateMessage: (message: Message) => void;
  updateMessagePartial: (message: Partial<Message>) => void;
  updateMessageText: (id: string, chunk: string) => void;
  clearMessages: () => void;
  removeMessages: (ids: string[]) => Promise<Message[]>;
  deleteSession: (id: string) => void;
  applyMessagePatch: (messageId: string, patch: MessagePatch) => void;
}
