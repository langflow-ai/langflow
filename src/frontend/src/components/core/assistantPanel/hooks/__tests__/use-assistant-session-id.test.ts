import { act, renderHook } from "@testing-library/react";
import { ASSISTANT_SESSION_STORAGE_KEY_PREFIX } from "../../assistant-panel.constants";
import { useAssistantSessionId } from "../use-assistant-session-id";

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

describe("useAssistantSessionId", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("session generation", () => {
    it("should generate a valid UUID session_id on first use", () => {
      const { result } = renderHook(() => useAssistantSessionId("flow-123"));

      expect(result.current.sessionId).toMatch(UUID_REGEX);
    });

    it("should persist session_id to localStorage", () => {
      const { result } = renderHook(() => useAssistantSessionId("flow-123"));

      const storageKey = `${ASSISTANT_SESSION_STORAGE_KEY_PREFIX}flow-123`;
      const stored = localStorage.getItem(storageKey);

      expect(stored).toBe(result.current.sessionId);
    });
  });

  describe("session persistence", () => {
    it("should return same session_id across re-renders", () => {
      const { result, rerender } = renderHook(() =>
        useAssistantSessionId("flow-123"),
      );

      const firstSessionId = result.current.sessionId;

      rerender();

      expect(result.current.sessionId).toBe(firstSessionId);
    });

    it("should restore session_id from localStorage", () => {
      const existingId = "pre-existing-session-id";
      const storageKey = `${ASSISTANT_SESSION_STORAGE_KEY_PREFIX}flow-123`;
      localStorage.setItem(storageKey, existingId);

      const { result } = renderHook(() => useAssistantSessionId("flow-123"));

      expect(result.current.sessionId).toBe(existingId);
    });
  });

  describe("flow scoping", () => {
    it("should generate different session_ids for different flows", () => {
      const { result: result1 } = renderHook(() =>
        useAssistantSessionId("flow-aaa"),
      );
      const { result: result2 } = renderHook(() =>
        useAssistantSessionId("flow-bbb"),
      );

      expect(result1.current.sessionId).not.toBe(result2.current.sessionId);
    });

    it("should update session_id when flowId changes", () => {
      const { result, rerender } = renderHook(
        ({ flowId }) => useAssistantSessionId(flowId),
        { initialProps: { flowId: "flow-aaa" } },
      );

      const firstSessionId = result.current.sessionId;

      rerender({ flowId: "flow-bbb" });

      expect(result.current.sessionId).not.toBe(firstSessionId);
      expect(result.current.sessionId).toMatch(UUID_REGEX);
    });

    it("should store each flow session_id independently", () => {
      renderHook(() => useAssistantSessionId("flow-aaa"));
      renderHook(() => useAssistantSessionId("flow-bbb"));

      const keyA = `${ASSISTANT_SESSION_STORAGE_KEY_PREFIX}flow-aaa`;
      const keyB = `${ASSISTANT_SESSION_STORAGE_KEY_PREFIX}flow-bbb`;

      expect(localStorage.getItem(keyA)).toBeTruthy();
      expect(localStorage.getItem(keyB)).toBeTruthy();
      expect(localStorage.getItem(keyA)).not.toBe(localStorage.getItem(keyB));
    });
  });

  describe("session reset", () => {
    it("should generate a new session_id on reset", () => {
      const { result } = renderHook(() => useAssistantSessionId("flow-123"));

      const originalSessionId = result.current.sessionId;

      act(() => {
        result.current.resetSessionId();
      });

      expect(result.current.sessionId).not.toBe(originalSessionId);
      expect(result.current.sessionId).toMatch(UUID_REGEX);
    });

    it("should persist the new session_id to localStorage after reset", () => {
      const { result } = renderHook(() => useAssistantSessionId("flow-123"));

      act(() => {
        result.current.resetSessionId();
      });

      const storageKey = `${ASSISTANT_SESSION_STORAGE_KEY_PREFIX}flow-123`;
      const stored = localStorage.getItem(storageKey);

      expect(stored).toBe(result.current.sessionId);
    });

    it("should not affect other flow sessions on reset", () => {
      const { result: resultA } = renderHook(() =>
        useAssistantSessionId("flow-aaa"),
      );
      const { result: resultB } = renderHook(() =>
        useAssistantSessionId("flow-bbb"),
      );

      const originalB = resultB.current.sessionId;

      act(() => {
        resultA.current.resetSessionId();
      });

      expect(resultB.current.sessionId).toBe(originalB);
    });
  });

  describe("edge cases", () => {
    it("should handle empty flowId", () => {
      const { result } = renderHook(() => useAssistantSessionId(""));

      expect(result.current.sessionId).toMatch(UUID_REGEX);

      const storageKey = `${ASSISTANT_SESSION_STORAGE_KEY_PREFIX}`;
      expect(localStorage.getItem(storageKey)).toBe(result.current.sessionId);
    });

    it("should provide a stable resetSessionId reference", () => {
      const { result, rerender } = renderHook(() =>
        useAssistantSessionId("flow-123"),
      );

      const firstResetFn = result.current.resetSessionId;

      rerender();

      expect(result.current.resetSessionId).toBe(firstResetFn);
    });
  });
});
