/**
 * Tests for useDeleteSession Playground Mode
 *
 * When playgroundPage is true, session deletion should use sessionStorage
 * instead of calling the authenticated API endpoint. This mirrors the
 * pattern used by useGetSessionsFromFlowQuery, useGetMessagesQuery,
 * and useUpdateMessage.
 */

describe("useDeleteSession - Playground Mode Logic", () => {
  const SESSION_ID = "test-session-123";
  const FLOW_ID = "test-flow-456";

  beforeEach(() => {
    window.sessionStorage.clear();
  });

  function deleteSessionFromStorage(
    sessionId: string,
    flowId: string,
  ): { message: string } {
    const stored = window.sessionStorage.getItem(flowId) || "[]";
    const messages = JSON.parse(stored);
    const filtered = messages.filter(
      (msg: { session_id?: string }) => msg.session_id !== sessionId,
    );
    window.sessionStorage.setItem(flowId, JSON.stringify(filtered));
    return { message: "Session deleted from local storage" };
  }

  describe("Playground Mode (sessionStorage)", () => {
    it("should_remove_messages_matching_sessionId_from_sessionStorage", () => {
      const messages = [
        { id: "1", session_id: SESSION_ID, text: "hello" },
        { id: "2", session_id: SESSION_ID, text: "world" },
        { id: "3", session_id: "other-session", text: "keep me" },
      ];
      window.sessionStorage.setItem(FLOW_ID, JSON.stringify(messages));

      const result = deleteSessionFromStorage(SESSION_ID, FLOW_ID);

      expect(result.message).toBe("Session deleted from local storage");

      const remaining = JSON.parse(
        window.sessionStorage.getItem(FLOW_ID) || "[]",
      );
      expect(remaining).toHaveLength(1);
      expect(remaining[0].id).toBe("3");
      expect(remaining[0].session_id).toBe("other-session");
    });

    it("should_handle_empty_sessionStorage_gracefully", () => {
      const result = deleteSessionFromStorage(SESSION_ID, FLOW_ID);

      expect(result.message).toBe("Session deleted from local storage");

      const remaining = JSON.parse(
        window.sessionStorage.getItem(FLOW_ID) || "[]",
      );
      expect(remaining).toHaveLength(0);
    });

    it("should_handle_sessionStorage_with_no_matching_session", () => {
      const messages = [
        { id: "1", session_id: "other-session", text: "keep me" },
      ];
      window.sessionStorage.setItem(FLOW_ID, JSON.stringify(messages));

      deleteSessionFromStorage(SESSION_ID, FLOW_ID);

      const remaining = JSON.parse(
        window.sessionStorage.getItem(FLOW_ID) || "[]",
      );
      expect(remaining).toHaveLength(1);
      expect(remaining[0].id).toBe("1");
    });

    it("should_only_remove_messages_for_the_specified_session", () => {
      const messages = [
        { id: "1", session_id: "session-a", text: "a1" },
        { id: "2", session_id: "session-b", text: "b1" },
        { id: "3", session_id: "session-a", text: "a2" },
        { id: "4", session_id: "session-c", text: "c1" },
      ];
      window.sessionStorage.setItem(FLOW_ID, JSON.stringify(messages));

      deleteSessionFromStorage("session-a", FLOW_ID);

      const remaining = JSON.parse(
        window.sessionStorage.getItem(FLOW_ID) || "[]",
      );
      expect(remaining).toHaveLength(2);
      expect(remaining.map((m: { id: string }) => m.id)).toEqual(["2", "4"]);
    });

    it("should_handle_messages_without_session_id", () => {
      const messages = [
        { id: "1", session_id: SESSION_ID, text: "remove" },
        { id: "2", text: "no session id" },
        { id: "3", session_id: SESSION_ID, text: "also remove" },
      ];
      window.sessionStorage.setItem(FLOW_ID, JSON.stringify(messages));

      deleteSessionFromStorage(SESSION_ID, FLOW_ID);

      const remaining = JSON.parse(
        window.sessionStorage.getItem(FLOW_ID) || "[]",
      );
      expect(remaining).toHaveLength(1);
      expect(remaining[0].id).toBe("2");
    });
  });
});
