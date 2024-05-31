import { create } from "zustand";
import { MessagesStoreType } from "../types/zustand/messages";

export const useMessagesStore = create<MessagesStoreType>((set, get) => ({
  messages: [],
  setMessages: (messages) => {
    set(() => ({ messages: messages }));
  },
  addMessage: (message) => {
    set(() => ({ messages: [...get().messages, message] }));
  },
  removeMessage: (message) => {
    set(() => ({
      messages: get().messages.filter((msg) => msg.id !== message.id),
    }));
  },
  updateMessage: (message) => {
    set(() => ({
      messages: get().messages.map((msg) =>
        msg.id === message.id ? message : msg,
      ),
    }));
  },
  clearMessages: () => {
    set(() => ({ messages: [] }));
  },
  removeMessages: (ids) => {
    return new Promise((resolve, reject) => {
      try {
        set((state) => {
          const updatedMessages = state.messages.filter(
            (msg) => !ids.includes(msg.index),
          );
          get().setMessages(updatedMessages);
          resolve(updatedMessages);
          return { messages: updatedMessages };
        });
      } catch (error) {
        reject(error);
      }
    });
  },
}));
