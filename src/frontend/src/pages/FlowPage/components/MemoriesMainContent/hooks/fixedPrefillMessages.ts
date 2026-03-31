export type PrefillFlowMessage = {
  id?: string;
  session_id?: string;
  sender?: string;
  text?: string;
  timestamp?: string;
};

const FIXED_SESSIONS = [
  "fixed-session-1",
  "fixed-session-2",
  "fixed-session-3",
] as const;

const MESSAGES_PER_SESSION = 20;

const buildTimestamp = (offsetSeconds: number) =>
  new Date(Date.UTC(2026, 2, 31, 0, 0, offsetSeconds)).toISOString();

export const FIXED_PREFILL_MESSAGES: PrefillFlowMessage[] =
  FIXED_SESSIONS.flatMap((sessionId, sessionIdx) =>
    Array.from({ length: MESSAGES_PER_SESSION }, (_, messageIdx) => {
      const indexWithinSession = messageIdx + 1;
      const globalOffsetSeconds =
        sessionIdx * MESSAGES_PER_SESSION + indexWithinSession;

      return {
        id: `fixed-${sessionId}-msg-${indexWithinSession}`,
        session_id: sessionId,
        sender: messageIdx % 2 === 0 ? "user" : "assistant",
        text: `Fixed prefill message ${indexWithinSession} (${sessionId})`,
        timestamp: buildTimestamp(globalOffsetSeconds),
      };
    }),
  );
