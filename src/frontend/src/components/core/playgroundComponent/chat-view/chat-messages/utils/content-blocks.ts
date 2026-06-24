import type { ChatMessageType, ContentBlockItem } from "@/types/chat";

/**
 * Content block utilities for determining state and loading status.
 */

export interface ContentBlockLayout {
  displayedContentBlocks: ContentBlockItem[];
  showBubbleBody: boolean;
  useContentBlockOrdering: boolean;
}

/**
 * Resolves how a message's content blocks and bubble body should render.
 *
 * content_blocks shows up in two shapes:
 *   - Legacy: an "Agent Steps" group wraps the tool calls (and the legacy
 *     agent also appends a flat TextContent at the top that duplicates
 *     Message.text). Render the group via the accordion and let the bubble
 *     body paint Message.text below — the historical "tools on top, text
 *     after" layout.
 *   - Interleaved (post agent-events rewiring): no group, just flat
 *     tool_use / citation / text items in producer order. Trust the
 *     content_blocks order and suppress the bubble body so text doesn't
 *     double-paint.
 * The signal is: a flat non-text block (tool_use, citation, …) with no
 * group present means the producer is making an ordering claim.
 */
export function resolveContentBlockLayout(
  contentBlocks: ContentBlockItem[],
  messageText: string | undefined,
  editMessage: boolean,
): ContentBlockLayout {
  const hasGroup = contentBlocks.some((block) => block.type === "group");
  const hasFlatNonText = contentBlocks.some(
    (block) => block.type !== "group" && block.type !== "text",
  );
  const hasTextBlock = contentBlocks.some((block) => block.type === "text");
  const useContentBlockOrdering = !hasGroup && hasFlatNonText;
  // Suppress the bubble body only when the content blocks actually carry the
  // answer text. If a producer emits only flat tool_use / citation items (no
  // TextContent) and stuffs the answer into Message.text, keep the bubble
  // body so the assistant text isn't hidden.
  const showBubbleBody =
    !useContentBlockOrdering || editMessage || !hasTextBlock;
  // In legacy / pure-text mode, strip a top-level TextContent only when it
  // duplicates Message.text — those items would render above the grouped
  // accordion. A divergent text block (text !== Message.text) is kept so it
  // isn't silently dropped.
  const displayedContentBlocks = useContentBlockOrdering
    ? contentBlocks
    : contentBlocks.filter(
        (block) => block.type !== "text" || block.text !== messageText,
      );
  return { displayedContentBlocks, showBubbleBody, useContentBlockOrdering };
}

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
