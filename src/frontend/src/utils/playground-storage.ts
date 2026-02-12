import type { Message } from "@/types/messages";

const MESSAGES_KEY_PREFIX = "langflow_playground_messages_";
const SESSIONS_KEY_PREFIX = "langflow_playground_sessions_";

export const getPlaygroundMessages = (flowId: string): Message[] => {
  try {
    const raw = localStorage.getItem(`${MESSAGES_KEY_PREFIX}${flowId}`);
    return raw ? (JSON.parse(raw) as Message[]) : [];
  } catch {
    return [];
  }
};

export const savePlaygroundMessages = (
  flowId: string,
  messages: Message[],
): void => {
  try {
    localStorage.setItem(
      `${MESSAGES_KEY_PREFIX}${flowId}`,
      JSON.stringify(messages),
    );
  } catch (error) {
    console.error("Failed to save playground messages to localStorage", error);
  }
};

export const getPlaygroundSessions = (flowId: string): string[] => {
  try {
    const raw = localStorage.getItem(`${SESSIONS_KEY_PREFIX}${flowId}`);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
};

export const savePlaygroundSessions = (
  flowId: string,
  sessions: string[],
): void => {
  try {
    localStorage.setItem(
      `${SESSIONS_KEY_PREFIX}${flowId}`,
      JSON.stringify(sessions),
    );
  } catch (error) {
    console.error("Failed to save playground sessions to localStorage", error);
  }
};

export const removePlaygroundSessionMessages = (
  flowId: string,
  sessionId: string,
): void => {
  const messages = getPlaygroundMessages(flowId);
  const filtered = messages.filter((msg) => msg.session_id !== sessionId);
  savePlaygroundMessages(flowId, filtered);
};
