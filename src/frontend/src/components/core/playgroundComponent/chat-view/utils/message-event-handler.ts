import type { Message } from "@/types/messages";
import { removeMessages, updateMessage } from "./message-utils";

/**
 * Handles message-related events from the build process.
 * This keeps all chat message logic within the chat-view scope.
 */
export const handleMessageEvent = (
  eventType: string,
  data: unknown,
): boolean => {
  switch (eventType) {
    case "add_message": {
      // Add/update message in React Query cache (replaces placeholder if exists)
      updateMessage(data as Message);
      return true;
    }
    case "token": {
      // Update message text in React Query cache for streaming
      updateMessage({
        id: data.id,
        flow_id: data.flow_id || "",
        session_id: data.session_id || "",
        text: data.chunk || "",
        sender: data.sender || "Machine",
        sender_name: data.sender_name || "AI",
        timestamp: data.timestamp || new Date().toISOString(),
        files: data.files || [],
        edit: data.edit || false,
        background_color: data.background_color || "",
        text_color: data.text_color || "",
        properties: { ...data.properties, state: "partial" },
      } as Message);
      return true;
    }
    case "remove_message": {
      // Remove message from React Query cache
      removeMessages([data.id], data.session_id || "", data.flow_id || "");
      return true;
    }
    case "error": {
      if (data?.category === "error") {
        // Add error message to React Query cache
        updateMessage(data as Message);
      }
      return true;
    }
    default:
      // Not a message event, return false to indicate it wasn't handled
      return false;
  }
};
