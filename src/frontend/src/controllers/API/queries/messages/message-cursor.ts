import type { Message } from "@/types/messages";

// The position to page below: a loaded message's timestamp and id, exactly as the
// API returned them. It carries values rather than referring to the message, so
// it still works after that message is deleted.
export interface MessageCursor {
  before_timestamp: string;
  before_id: string;
}

export const cursorBelow = (
  message: Pick<Message, "id" | "timestamp"> | undefined,
): MessageCursor | undefined =>
  message?.id
    ? { before_timestamp: message.timestamp, before_id: message.id }
    : undefined;
