import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";
import { removeMessages, updateMessage } from "./message-utils";

/**
 * Handles message-related events from the build process.
 * Updates both React Query cache (used by the internal playground)
 * and useMessagesStore (used by the shareable playground / IOModal).
 */
export const handleMessageEvent = (
  eventType: string,
  data: unknown,
): boolean => {
  switch (eventType) {
    case "add_message": {
      // Update React Query cache (internal playground)
      updateMessage(data as Message);
      // Update Zustand store (shareable playground / IOModal)
      useMessagesStore.getState().addMessage(data as Message);
      return true;
    }
    case "token": {
      const d = data as Record<string, unknown>;
      const tokenMessage = {
        id: d.id,
        flow_id: d.flow_id || "",
        session_id: d.session_id || "",
        text: d.chunk || "",
        sender: d.sender || "Machine",
        sender_name: d.sender_name || "AI",
        timestamp: d.timestamp || new Date().toISOString(),
        files: d.files || [],
        edit: d.edit || false,
        background_color: d.background_color || "",
        text_color: d.text_color || "",
        properties: { ...(d.properties as object), state: "partial" },
      } as Message;
      // Update React Query cache (internal playground)
      updateMessage(tokenMessage);
      // Update Zustand store (shareable playground / IOModal)
      useMessagesStore.getState().addMessage(tokenMessage);
      return true;
    }
    case "remove_message": {
      const rm = data as Record<string, string>;
      // Remove from React Query cache
      removeMessages([rm.id], rm.session_id || "", rm.flow_id || "");
      // Remove from Zustand store
      useMessagesStore.getState().removeMessage(data as Message);
      return true;
    }
    case "error": {
      if ((data as Record<string, unknown>)?.category === "error") {
        // Update React Query cache
        updateMessage(data as Message);
        // Update Zustand store
        useMessagesStore.getState().addMessage(data as Message);
      }
      return true;
    }
    default:
      // Not a message event, return false to indicate it wasn't handled
      return false;
  }
};
