import { create } from "zustand";
import { MessagesStoreType } from "../types/zustand/messages";

export const useMessagesStore = create<MessagesStoreType>((set, get) => ({
  displayLoadingMessage: false,
  deleteSession: (id) => {
    set((state) => {
      const updatedMessages = state.messages.filter(
        (msg) => msg.session_id !== id,
      );
      return { messages: updatedMessages };
    });
  },
  messages: [],
  setMessages: (messages) => {
    set(() => ({ messages: messages }));
  },
  addMessage: (message) => {
    const existingMessage = get().messages.find((msg) => msg.id === message.id);
    if (existingMessage) {
      // Check if this is a streaming partial message (state: "partial")
      if (message.properties?.state === "partial") {
        // For streaming, accumulate the text content since backend now sends individual chunks
        // But first check if this chunk would create duplication
        const currentText = existingMessage.text || "";
        const newChunk = message.text || "";

        // Only add the chunk if it's not already at the end of the current text
        // This prevents duplication when the same chunk is sent multiple times
        if (newChunk && !currentText.endsWith(newChunk)) {
          get().updateMessageText(message.id, newChunk);
        }

        // Update other properties but preserve accumulated text
        const { text, ...messageWithoutText } = message;
        get().updateMessagePartial(messageWithoutText);
      } else {
        // For complete messages, replace entirely
        get().updateMessagePartial(message);
      }
      return;
    }
    if (message.sender === "Machine") {
      set(() => ({ displayLoadingMessage: false }));
    }
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
    set((state) => {
      const updatedMessages = [...state.messages];
      for (let i = state.messages.length - 1; i >= 0; i--) {
        if (state.messages[i].id === message.id) {
          updatedMessages[i] = { ...updatedMessages[i], ...message };
          break;
        }
      }
      return { messages: updatedMessages };
    });
  },
  updateMessageText: (id, chunk) => {
    set((state) => {
      const updatedMessages = [...state.messages];
      for (let i = state.messages.length - 1; i >= 0; i--) {
        if (state.messages[i].id === id) {
          updatedMessages[i] = {
            ...updatedMessages[i],
            text: (updatedMessages[i].text || "") + chunk,
          };
          break;
        }
      }
      return { messages: updatedMessages };
    });
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
