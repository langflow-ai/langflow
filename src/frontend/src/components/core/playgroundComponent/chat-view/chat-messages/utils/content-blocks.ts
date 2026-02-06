import type { ChatMessageType } from "@/types/chat";

/**
 * Content block utilities for determining state and loading status.
 */

/**
 * Determines if content blocks are in a loading state.
 *
 * @param chat - The chat message
 * @param isBuilding - Whether the flow is currently building
 * @param lastMessage - Whether this is the last message
 * @returns True if content blocks are loading
 */
export function getContentBlockLoadingState(
  chat: ChatMessageType,
  isBuilding: boolean,
  lastMessage: boolean,
): boolean {
  return (
    isBuilding &&
    lastMessage &&
    (!chat.content_blocks ||
      chat.content_blocks.length === 0 ||
      chat.properties?.state === "partial")
  );
}

/**
 * Gets the state for content blocks display.
 *
 * @param chat - The chat message
 * @param isBuilding - Whether the flow is currently building
 * @param lastMessage - Whether this is the last message
 * @returns The state string or undefined
 */
export function getContentBlockState(
  chat: ChatMessageType,
  isBuilding: boolean,
  lastMessage: boolean,
): string | undefined {
  return (
    chat.properties?.state ||
    (isBuilding && lastMessage ? "partial" : undefined)
  );
}
