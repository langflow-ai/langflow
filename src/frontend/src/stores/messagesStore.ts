import { create } from "zustand";
import { MessagesStoreType } from "../types/zustand/messages";

export const useMessagesStore = create<MessagesStoreType>((set, get) => ({
  deleteSession: (id) => {
    set((state) => {
      const updatedMessages = state.messages.filter(
        (msg) => msg.session_id !== id,
      );
      return { messages: updatedMessages };
    });
  },
  columns: [],
  setColumns: (columns) => {
    set(() => ({ columns: columns }));
  },
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
  updateMessagePartial: (message) => {
    // search for the message and update it
    // look for the message list backwards to find the message faster
    for (let i = get().messages.length - 1; i >= 0; i--) {
      if (get().messages[i].id === message.id) {
        set((state) => {
          const updatedMessages = [...state.messages];
          updatedMessages[i] = { ...updatedMessages[i], ...message };
          return { messages: updatedMessages };
        });
        break;
      }
    }

  },
  clearMessages: () => {
    set(() => ({ messages: [] }));
  },
  removeMessages: (ids) => {
    return new Promise((resolve, reject) => {
      try {
        set((state) => {
          const updatedMessages = state.messages.filter(
            (msg) => !ids.includes(msg.id),
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
