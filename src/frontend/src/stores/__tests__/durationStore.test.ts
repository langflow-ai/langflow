import { act, renderHook } from "@testing-library/react";

// Mock clearInterval to track calls
const mockClearInterval = jest.fn();
global.clearInterval = mockClearInterval;

import { useDurationStore } from "../durationStore";

describe("useDurationStore", () => {
  beforeEach(() => {
    // Clear all mocks
    jest.clearAllMocks();
    mockClearInterval.mockClear();

    // Reset store state
    useDurationStore.setState({
      durations: {},
      intervals: {},
      startTimes: {},
    });
  });

  describe("initial state", () => {
    it("should initialize with empty durations, intervals, and startTimes", () => {
      const { result } = renderHook(() => useDurationStore());

      expect(result.current.durations).toEqual({});
      expect(result.current.intervals).toEqual({});
      expect(result.current.startTimes).toEqual({});
    });
  });

  describe("setDuration", () => {
    it("should set duration for a chat ID", () => {
      const { result } = renderHook(() => useDurationStore());

      act(() => {
        result.current.setDuration("chat-1", 100);
      });

      expect(result.current.durations).toEqual({
        "chat-1": 100,
      });
    });

    it("should set durations for multiple chat IDs", () => {
      const { result } = renderHook(() => useDurationStore());

      act(() => {
        result.current.setDuration("chat-1", 100);
        result.current.setDuration("chat-2", 200);
        result.current.setDuration("chat-3", 300);
      });

      expect(result.current.durations).toEqual({
        "chat-1": 100,
        "chat-2": 200,
        "chat-3": 300,
      });
    });

    it("should overwrite existing duration for same chat ID", () => {
      const { result } = renderHook(() => useDurationStore());

      act(() => {
        result.current.setDuration("chat-1", 100);
      });

      expect(result.current.durations["chat-1"]).toBe(100);

      act(() => {
        result.current.setDuration("chat-1", 500);
      });

      expect(result.current.durations["chat-1"]).toBe(500);
    });

    it("should handle zero duration", () => {
      const { result } = renderHook(() => useDurationStore());

      act(() => {
        result.current.setDuration("chat-1", 0);
      });

      expect(result.current.durations["chat-1"]).toBe(0);
    });

    it("should handle negative duration", () => {
      const { result } = renderHook(() => useDurationStore());

      act(() => {
        result.current.setDuration("chat-1", -50);
      });

      expect(result.current.durations["chat-1"]).toBe(-50);
    });

    it("should handle very large duration values", () => {
      const { result } = renderHook(() => useDurationStore());
      const largeDuration = Number.MAX_SAFE_INTEGER;

      act(() => {
        result.current.setDuration("chat-1", largeDuration);
      });

      expect(result.current.durations["chat-1"]).toBe(largeDuration);
    });
  });

  describe("startTimer", () => {
    beforeEach(() => {
      jest.useFakeTimers();
      jest.setSystemTime(new Date("2024-01-01T00:00:00.000Z"));
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it("should start timer for new chat ID with Date.now()", () => {
      const { result } = renderHook(() => useDurationStore());
      const expectedTime = Date.now();

      act(() => {
        result.current.startTimer("chat-1");
      });

      expect(result.current.startTimes["chat-1"]).toBe(expectedTime);
      expect(result.current.durations["chat-1"]).toBe(0);
    });

    it("should reset timer for existing chat ID", () => {
      const { result } = renderHook(() => useDurationStore());

      act(() => {
        result.current.setDuration("chat-1", 5000);
        result.current.startTimer("chat-1");
      });

      expect(result.current.durations["chat-1"]).toBe(0);
      expect(result.current.startTimes["chat-1"]).toBe(Date.now());
    });

    it("should handle multiple chat IDs independently", () => {
      const { result } = renderHook(() => useDurationStore());
      const time1 = Date.now();

      act(() => {
        result.current.startTimer("chat-1");
      });

      // Advance time
      jest.advanceTimersByTime(1000);
      const time2 = Date.now();

      act(() => {
        result.current.startTimer("chat-2");
      });

      expect(result.current.startTimes["chat-1"]).toBe(time1);
      expect(result.current.startTimes["chat-2"]).toBe(time2);
      expect(result.current.durations).toEqual({
        "chat-1": 0,
        "chat-2": 0,
      });
    });
  });

  describe("setInterval", () => {
    it("should set interval for a chat ID", () => {
      const { result } = renderHook(() => useDurationStore());
      const mockInterval = setInterval(() => {}, 1000) as NodeJS.Timeout;

      act(() => {
        result.current.setInterval("chat-1", mockInterval);
      });

      expect(result.current.intervals["chat-1"]).toBe(mockInterval);

      // Clean up
      clearInterval(mockInterval);
    });

    it("should set intervals for multiple chat IDs", () => {
      const { result } = renderHook(() => useDurationStore());
      const mockInterval1 = setInterval(() => {}, 1000) as NodeJS.Timeout;
      const mockInterval2 = setInterval(() => {}, 1000) as NodeJS.Timeout;

      act(() => {
        result.current.setInterval("chat-1", mockInterval1);
        result.current.setInterval("chat-2", mockInterval2);
      });

      expect(result.current.intervals).toEqual({
        "chat-1": mockInterval1,
        "chat-2": mockInterval2,
      });

      // Clean up
      clearInterval(mockInterval1);
      clearInterval(mockInterval2);
    });

    it("should overwrite existing interval for same chat ID", () => {
      const { result } = renderHook(() => useDurationStore());
      const mockInterval1 = setInterval(() => {}, 1000) as NodeJS.Timeout;
      const mockInterval2 = setInterval(() => {}, 1000) as NodeJS.Timeout;

      act(() => {
        result.current.setInterval("chat-1", mockInterval1);
      });

      expect(result.current.intervals["chat-1"]).toBe(mockInterval1);

      act(() => {
        result.current.setInterval("chat-1", mockInterval2);
      });

      expect(result.current.intervals["chat-1"]).toBe(mockInterval2);

      // Clean up
      clearInterval(mockInterval1);
      clearInterval(mockInterval2);
    });
  });

  describe("clearInterval", () => {
    it("should clear interval for existing chat ID", () => {
      const { result } = renderHook(() => useDurationStore());
      const mockInterval = setInterval(() => {}, 1000) as NodeJS.Timeout;

      act(() => {
        result.current.setInterval("chat-1", mockInterval);
      });

      expect(result.current.intervals["chat-1"]).toBe(mockInterval);

      act(() => {
        result.current.clearInterval("chat-1");
      });

      expect(result.current.intervals["chat-1"]).toBeUndefined();
      expect(result.current.startTimes["chat-1"]).toBeUndefined();
      expect(mockClearInterval).toHaveBeenCalledWith(mockInterval);
    });

    it("should handle clearing non-existent chat ID gracefully", () => {
      const { result } = renderHook(() => useDurationStore());

      act(() => {
        result.current.clearInterval("non-existent-chat");
      });

      expect(result.current.intervals).toEqual({});
      expect(mockClearInterval).not.toHaveBeenCalled();
    });

    it("should only remove specified chat ID interval", () => {
      const { result } = renderHook(() => useDurationStore());
      const mockInterval1 = setInterval(() => {}, 1000) as NodeJS.Timeout;
      const mockInterval2 = setInterval(() => {}, 1000) as NodeJS.Timeout;

      act(() => {
        result.current.setInterval("chat-1", mockInterval1);
        result.current.setInterval("chat-2", mockInterval2);
      });

      act(() => {
        result.current.clearInterval("chat-1");
      });

      expect(result.current.intervals).toEqual({
        "chat-2": mockInterval2,
      });
      expect(mockClearInterval).toHaveBeenCalledWith(mockInterval1);

      // Clean up
      clearInterval(mockInterval2);
    });

    it("should handle multiple clearInterval calls for same chat ID", () => {
      const { result } = renderHook(() => useDurationStore());
      const mockInterval = setInterval(() => {}, 1000) as NodeJS.Timeout;

      act(() => {
        result.current.setInterval("chat-1", mockInterval);
        result.current.clearInterval("chat-1");
        result.current.clearInterval("chat-1"); // Second call should be safe
      });

      expect(result.current.intervals["chat-1"]).toBeUndefined();
      expect(mockClearInterval).toHaveBeenCalledTimes(1);
    });
  });

  describe("integration scenarios", () => {
    it("should handle complete chat session lifecycle", () => {
      const { result } = renderHook(() => useDurationStore());
      const mockInterval = setInterval(() => {}, 1000) as NodeJS.Timeout;

      // Start chat session
      act(() => {
        result.current.setDuration("chat-session-1", 0);
        result.current.setInterval("chat-session-1", mockInterval);
      });

      expect(result.current.durations["chat-session-1"]).toBe(0);
      expect(result.current.intervals["chat-session-1"]).toBe(mockInterval);

      // Simulate timer with startTimer
      act(() => {
        result.current.startTimer("chat-session-1");
        result.current.setDuration("chat-session-1", 30);
      });

      expect(result.current.durations["chat-session-1"]).toBe(30);

      // End chat session
      act(() => {
        result.current.clearInterval("chat-session-1");
      });

      expect(result.current.intervals["chat-session-1"]).toBeUndefined();
      expect(result.current.durations["chat-session-1"]).toBe(30); // Duration should persist
      expect(mockClearInterval).toHaveBeenCalledWith(mockInterval);
    });

    it("should handle multiple concurrent chat sessions", () => {
      const { result } = renderHook(() => useDurationStore());
      const mockInterval1 = setInterval(() => {}, 1000) as NodeJS.Timeout;
      const mockInterval2 = setInterval(() => {}, 1000) as NodeJS.Timeout;
      const mockInterval3 = setInterval(() => {}, 1000) as NodeJS.Timeout;

      // Start multiple sessions
      act(() => {
        result.current.setDuration("chat-1", 0);
        result.current.setDuration("chat-2", 0);
        result.current.setDuration("chat-3", 0);
        result.current.setInterval("chat-1", mockInterval1);
        result.current.setInterval("chat-2", mockInterval2);
        result.current.setInterval("chat-3", mockInterval3);
      });

      // Simulate different progress for each chat
      act(() => {
        result.current.setDuration("chat-1", 10);
        result.current.setDuration("chat-2", 20);
        result.current.setDuration("chat-3", 30);
      });

      expect(result.current.durations).toEqual({
        "chat-1": 10,
        "chat-2": 20,
        "chat-3": 30,
      });

      // End one session
      act(() => {
        result.current.clearInterval("chat-2");
      });

      expect(result.current.intervals).toEqual({
        "chat-1": mockInterval1,
        "chat-3": mockInterval3,
      });

      // Clean up
      clearInterval(mockInterval1);
      clearInterval(mockInterval3);
    });

    it("should handle session restart", () => {
      const { result } = renderHook(() => useDurationStore());
      const mockInterval1 = setInterval(() => {}, 1000) as NodeJS.Timeout;
      const mockInterval2 = setInterval(() => {}, 1000) as NodeJS.Timeout;

      // Start session
      act(() => {
        result.current.startTimer("chat-1");
        result.current.setInterval("chat-1", mockInterval1);
        result.current.setDuration("chat-1", 20);
      });

      expect(result.current.durations["chat-1"]).toBe(20);

      // Restart session with new interval
      act(() => {
        result.current.clearInterval("chat-1");
        result.current.startTimer("chat-1");
        result.current.setInterval("chat-1", mockInterval2);
      });

      expect(result.current.durations["chat-1"]).toBe(0);
      expect(result.current.intervals["chat-1"]).toBe(mockInterval2);
      expect(result.current.startTimes["chat-1"]).toBeDefined();
      expect(mockClearInterval).toHaveBeenCalledWith(mockInterval1);

      // Clean up
      clearInterval(mockInterval2);
    });
  });

  describe("edge cases", () => {
    it("should handle empty string chat IDs", () => {
      const { result } = renderHook(() => useDurationStore());

      act(() => {
        result.current.setDuration("", 100);
        result.current.startTimer("");
      });

      expect(result.current.durations[""]).toBe(0);
      expect(result.current.startTimes[""]).toBeDefined();
    });

    it("should handle special character chat IDs", () => {
      const { result } = renderHook(() => useDurationStore());
      const specialChatId = "chat-@#$%^&*()_+{}[]|\\:;\"'<>?,./";

      act(() => {
        result.current.setDuration(specialChatId, 50);
        result.current.startTimer(specialChatId);
      });

      expect(result.current.durations[specialChatId]).toBe(0);
      expect(result.current.startTimes[specialChatId]).toBeDefined();
    });

    it("should handle very long chat IDs", () => {
      const { result } = renderHook(() => useDurationStore());
      const longChatId = "a".repeat(1000);

      act(() => {
        result.current.setDuration(longChatId, 25);
        result.current.startTimer(longChatId);
      });

      expect(result.current.durations[longChatId]).toBe(0);
      expect(result.current.startTimes[longChatId]).toBeDefined();
    });

    it("should handle rapid successive operations", () => {
      const { result } = renderHook(() => useDurationStore());
      const mockInterval = setInterval(() => {}, 1000) as NodeJS.Timeout;

      act(() => {
        // Rapid operations
        result.current.startTimer("rapid-chat");
        result.current.setInterval("rapid-chat", mockInterval);
        result.current.setDuration("rapid-chat", 100);
        result.current.clearInterval("rapid-chat");
      });

      expect(result.current.durations["rapid-chat"]).toBe(100);
      expect(result.current.intervals["rapid-chat"]).toBeUndefined();
      expect(mockClearInterval).toHaveBeenCalledWith(mockInterval);
    });

    it("should handle state persistence after operations", () => {
      const { result } = renderHook(() => useDurationStore());

      // Build up some state
      act(() => {
        result.current.setDuration("persistent-1", 100);
        result.current.setDuration("persistent-2", 200);
      });

      const durations = result.current.durations;

      // Operations on one chat shouldn't affect others
      act(() => {
        result.current.setDuration("persistent-3", 300);
      });

      expect(result.current.durations["persistent-1"]).toBe(100);
      expect(result.current.durations["persistent-2"]).toBe(200);
      expect(result.current.durations["persistent-3"]).toBe(300);
    });
  });

  describe("memory management", () => {
    it("should not have memory leaks when clearing intervals", () => {
      const { result } = renderHook(() => useDurationStore());
      const intervals: NodeJS.Timeout[] = [];

      // Create multiple intervals
      act(() => {
        for (let i = 0; i < 5; i++) {
          const interval = setInterval(() => {}, 1000) as NodeJS.Timeout;
          intervals.push(interval);
          result.current.setInterval(`chat-${i}`, interval);
        }
      });

      expect(Object.keys(result.current.intervals)).toHaveLength(5);

      // Clear all intervals
      act(() => {
        for (let i = 0; i < 5; i++) {
          result.current.clearInterval(`chat-${i}`);
        }
      });

      expect(Object.keys(result.current.intervals)).toHaveLength(0);
      expect(mockClearInterval).toHaveBeenCalledTimes(5);
    });
  });
});
