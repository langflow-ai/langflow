import { act, renderHook } from "@testing-library/react";
import type { AssistantMessage } from "../../assistant-panel.types";
import { useSessionHistory } from "../use-session-history";

// --- localStorage mock ---
const store: Record<string, string> = {};
const localStorageMock = {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, value: string) => {
    store[key] = value;
  },
  removeItem: (key: string) => {
    delete store[key];
  },
  clear: () => {
    for (const key in store) delete store[key];
  },
};

Object.defineProperty(window, "localStorage", {
  value: localStorageMock,
  writable: true,
});

// --- Helpers ---
const STORAGE_KEY = "langflow-assistant-sessions";
const SAMPLE_DATE = new Date("2026-03-20T10:00:00Z");

function createMessage(
  overrides?: Partial<AssistantMessage>,
): AssistantMessage {
  return {
    id: "msg-1",
    role: "user",
    content: "hello",
    timestamp: SAMPLE_DATE,
    status: "complete",
    ...overrides,
  };
}

describe("useSessionHistory", () => {
  let mockLoadSession: jest.Mock;

  beforeEach(() => {
    localStorageMock.clear();
    mockLoadSession = jest.fn();
  });

  describe("initial state", () => {
    it("should_start_with_empty_sessions_when_no_storage", () => {
      const { result } = renderHook(() =>
        useSessionHistory("s1", [], mockLoadSession),
      );

      expect(result.current.sessions).toEqual([]);
    });

    it("should_load_sessions_from_localStorage_on_mount", () => {
      const entry = {
        sessionId: "s1",
        firstUserMessage: "hello",
        messageCount: 1,
        lastActiveAt: SAMPLE_DATE.toISOString(),
        messages: [],
      };
      localStorageMock.setItem(STORAGE_KEY, JSON.stringify([entry]));

      const { result } = renderHook(() =>
        useSessionHistory("s2", [], mockLoadSession),
      );

      expect(result.current.sessions).toHaveLength(1);
      expect(result.current.sessions[0].sessionId).toBe("s1");
    });
  });

  describe("saveCurrentSession", () => {
    it("should_save_session_with_first_user_message_as_preview", () => {
      const messages = [
        createMessage({ content: "Create a component" }),
        createMessage({ id: "msg-2", role: "assistant", content: "Done" }),
      ];

      const { result } = renderHook(() =>
        useSessionHistory("s1", messages, mockLoadSession),
      );

      act(() => result.current.saveCurrentSession());

      expect(result.current.sessions).toHaveLength(1);
      expect(result.current.sessions[0].firstUserMessage).toBe(
        "Create a component",
      );
      expect(result.current.sessions[0].messageCount).toBe(2);
    });

    it("should_not_save_when_messages_are_empty", () => {
      const { result } = renderHook(() =>
        useSessionHistory("s1", [], mockLoadSession),
      );

      act(() => result.current.saveCurrentSession());

      expect(result.current.sessions).toHaveLength(0);
    });

    it("should_update_in_place_when_session_already_exists", () => {
      const messages1 = [createMessage({ content: "first" })];
      const { result, rerender } = renderHook(
        ({ msgs }) => useSessionHistory("s1", msgs, mockLoadSession),
        { initialProps: { msgs: messages1 } },
      );

      act(() => result.current.saveCurrentSession());
      expect(result.current.sessions[0].firstUserMessage).toBe("first");

      const messages2 = [
        createMessage({ content: "first" }),
        createMessage({ id: "m2", content: "second" }),
      ];
      rerender({ msgs: messages2 });

      act(() => result.current.saveCurrentSession());
      expect(result.current.sessions).toHaveLength(1);
      expect(result.current.sessions[0].messageCount).toBe(2);
    });

    it("should_add_new_session_to_top", () => {
      const entry = {
        sessionId: "old",
        firstUserMessage: "old msg",
        messageCount: 1,
        lastActiveAt: SAMPLE_DATE.toISOString(),
        messages: [],
      };
      localStorageMock.setItem(STORAGE_KEY, JSON.stringify([entry]));

      const messages = [createMessage({ content: "new msg" })];
      const { result } = renderHook(() =>
        useSessionHistory("new-session", messages, mockLoadSession),
      );

      act(() => result.current.saveCurrentSession());

      expect(result.current.sessions).toHaveLength(2);
      expect(result.current.sessions[0].sessionId).toBe("new-session");
      expect(result.current.sessions[1].sessionId).toBe("old");
    });

    it("should_cap_at_max_sessions", () => {
      const existingSessions = Array.from({ length: 10 }, (_, i) => ({
        sessionId: `s${i}`,
        firstUserMessage: `msg ${i}`,
        messageCount: 1,
        lastActiveAt: SAMPLE_DATE.toISOString(),
        messages: [],
      }));
      localStorageMock.setItem(STORAGE_KEY, JSON.stringify(existingSessions));

      const messages = [createMessage({ content: "overflow" })];
      const { result } = renderHook(() =>
        useSessionHistory("s-new", messages, mockLoadSession),
      );

      act(() => result.current.saveCurrentSession());

      expect(result.current.sessions).toHaveLength(10);
      expect(result.current.sessions[0].sessionId).toBe("s-new");
    });

    it("should_persist_to_localStorage", () => {
      const messages = [createMessage({ content: "persisted" })];
      const { result } = renderHook(() =>
        useSessionHistory("s1", messages, mockLoadSession),
      );

      act(() => result.current.saveCurrentSession());

      const stored = JSON.parse(localStorageMock.getItem(STORAGE_KEY) || "[]");
      expect(stored).toHaveLength(1);
      expect(stored[0].sessionId).toBe("s1");
    });
  });

  describe("switchSession", () => {
    it("should_call_loadSession_with_deserialized_messages", () => {
      const entry = {
        sessionId: "target",
        firstUserMessage: "hello",
        messageCount: 1,
        lastActiveAt: SAMPLE_DATE.toISOString(),
        messages: [
          {
            id: "m1",
            role: "user" as const,
            content: "hello",
            timestamp: SAMPLE_DATE.toISOString(),
            status: "complete" as const,
          },
        ],
      };
      localStorageMock.setItem(STORAGE_KEY, JSON.stringify([entry]));

      const { result } = renderHook(() =>
        useSessionHistory("current", [], mockLoadSession),
      );

      act(() => result.current.switchSession("target"));

      expect(mockLoadSession).toHaveBeenCalledWith(
        "target",
        expect.arrayContaining([
          expect.objectContaining({
            id: "m1",
            content: "hello",
          }),
        ]),
      );
    });

    it("should_not_call_loadSession_for_nonexistent_session", () => {
      const { result } = renderHook(() =>
        useSessionHistory("s1", [], mockLoadSession),
      );

      act(() => result.current.switchSession("nonexistent"));

      expect(mockLoadSession).not.toHaveBeenCalled();
    });
  });

  describe("deleteSession", () => {
    it("should_remove_session_from_list", () => {
      const entries = [
        {
          sessionId: "s1",
          firstUserMessage: "one",
          messageCount: 1,
          lastActiveAt: SAMPLE_DATE.toISOString(),
          messages: [],
        },
        {
          sessionId: "s2",
          firstUserMessage: "two",
          messageCount: 1,
          lastActiveAt: SAMPLE_DATE.toISOString(),
          messages: [],
        },
      ];
      localStorageMock.setItem(STORAGE_KEY, JSON.stringify(entries));

      const { result } = renderHook(() =>
        useSessionHistory("active", [], mockLoadSession),
      );

      act(() => result.current.deleteSession("s1"));

      expect(result.current.sessions).toHaveLength(1);
      expect(result.current.sessions[0].sessionId).toBe("s2");
    });

    it("should_persist_deletion_to_localStorage", () => {
      const entries = [
        {
          sessionId: "s1",
          firstUserMessage: "one",
          messageCount: 1,
          lastActiveAt: SAMPLE_DATE.toISOString(),
          messages: [],
        },
      ];
      localStorageMock.setItem(STORAGE_KEY, JSON.stringify(entries));

      const { result } = renderHook(() =>
        useSessionHistory("active", [], mockLoadSession),
      );

      act(() => result.current.deleteSession("s1"));

      const stored = JSON.parse(localStorageMock.getItem(STORAGE_KEY) || "[]");
      expect(stored).toEqual([]);
    });

    it("should_handle_deleting_nonexistent_session_gracefully", () => {
      const { result } = renderHook(() =>
        useSessionHistory("s1", [], mockLoadSession),
      );

      act(() => result.current.deleteSession("nonexistent"));

      expect(result.current.sessions).toEqual([]);
    });
  });
});
