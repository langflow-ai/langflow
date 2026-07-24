import ShortUniqueId from "short-unique-id";
import type { AssistantMessage } from "../assistant-panel.types";

const uid = new ShortUniqueId();

/**
 * Slash commands (/skip-all, /history, /iterations) echo the user input then a
 * same-turn ack; they never hit the backend. Shared so every command renders
 * one consistent shape.
 */
export function commandAckMessages(
  echoContent: string,
  announcement: string,
): AssistantMessage[] {
  return [
    {
      id: uid.randomUUID(10),
      role: "user",
      content: echoContent,
      timestamp: new Date(),
      status: "complete",
    },
    {
      id: uid.randomUUID(10),
      role: "assistant",
      content: announcement,
      timestamp: new Date(),
      status: "complete",
    },
  ];
}
