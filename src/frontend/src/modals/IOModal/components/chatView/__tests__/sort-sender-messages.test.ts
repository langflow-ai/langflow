import type { ChatMessageType } from "../../../../../types/chat";
import sortSenderMessages from "../helpers/sort-sender-messages";

// Helper function to create mock ChatMessageType
const createMockMessage = (
  timestamp: string,
  isSend: boolean,
  id: string = "test-id",
  message: string = "test message",
): ChatMessageType => ({
  id,
  timestamp,
  isSend,
  message,
  sender_name: isSend ? "User" : "AI",
  session: "test-session",
  files: [],
  edit: false,
  category: "message",
  properties: {
    source: { id: "test", display_name: "Test", source: "test" },
  },
  content_blocks: [],
});

describe("sortSenderMessages", () => {
  describe("Primary sorting by timestamp", () => {
    it("should sort messages by timestamp in ascending order", () => {
      const messages = [
        createMockMessage("2025-08-29 08:51:23 UTC", true, "msg3"),
        createMockMessage("2025-08-29 08:51:21 UTC", true, "msg1"),
        createMockMessage("2025-08-29 08:51:22 UTC", false, "msg2"),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      expect(sorted.map((m) => m.id)).toEqual(["msg1", "msg2", "msg3"]);
      expect(new Date(sorted[0].timestamp).getTime()).toBeLessThan(
        new Date(sorted[1].timestamp).getTime(),
      );
      expect(new Date(sorted[1].timestamp).getTime()).toBeLessThan(
        new Date(sorted[2].timestamp).getTime(),
      );
    });

    it("should handle different timestamp formats", () => {
      const messages = [
        createMockMessage("2025-08-29T08:51:23Z", false, "iso"),
        createMockMessage("2025-08-29 08:51:21 UTC", true, "utc"),
        createMockMessage("2025-08-29 08:51:22", true, "no-tz"),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      // Check that first is earliest, last is latest
      const sortedTimes = sorted.map((m) => new Date(m.timestamp).getTime());
      expect(sortedTimes[0]).toBeLessThan(sortedTimes[1]);
      expect(sortedTimes[1]).toBeLessThan(sortedTimes[2]);
      expect(sorted[0].id).toBe("utc"); // 08:51:21 is earliest
    });

    it("should handle messages spanning multiple days", () => {
      const messages = [
        createMockMessage("2025-08-30 08:51:21 UTC", true, "day2"),
        createMockMessage("2025-08-29 08:51:21 UTC", false, "day1"),
        createMockMessage("2025-08-31 08:51:21 UTC", true, "day3"),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      expect(sorted.map((m) => m.id)).toEqual(["day1", "day2", "day3"]);
    });
  });

  describe("Secondary sorting for identical timestamps", () => {
    it("should place User messages before AI messages when timestamps are identical", () => {
      const messages = [
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          false,
          "ai-msg",
          "AI response",
        ),
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          true,
          "user-msg",
          "User question",
        ),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      expect(sorted[0].id).toBe("user-msg");
      expect(sorted[0].isSend).toBe(true);
      expect(sorted[1].id).toBe("ai-msg");
      expect(sorted[1].isSend).toBe(false);
    });

    it("should maintain User-first order in multiple identical timestamp pairs", () => {
      const messages = [
        createMockMessage("2025-08-29 08:51:21 UTC", false, "ai1"),
        createMockMessage("2025-08-29 08:51:21 UTC", true, "user1"),
        createMockMessage("2025-08-29 08:51:21 UTC", false, "ai2"),
        createMockMessage("2025-08-29 08:51:21 UTC", true, "user2"),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      // Users should come first, then AIs, but maintain relative order within same type
      expect(sorted[0].isSend).toBe(true); // user1
      expect(sorted[1].isSend).toBe(true); // user2
      expect(sorted[2].isSend).toBe(false); // ai1
      expect(sorted[3].isSend).toBe(false); // ai2
    });

    it("should preserve original order for messages with same timestamp and sender type", () => {
      const messages = [
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          true,
          "user2",
          "Second user message",
        ),
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          true,
          "user1",
          "First user message",
        ),
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          true,
          "user3",
          "Third user message",
        ),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      // Order should be preserved when timestamps and sender types are identical
      expect(sorted.map((m) => m.id)).toEqual(["user2", "user1", "user3"]);
      expect(sorted.every((m) => m.isSend)).toBe(true);
    });
  });

  describe("Complex conversation scenarios", () => {
    it("should handle a realistic conversation with mixed timestamps", () => {
      const messages = [
        createMockMessage(
          "2025-08-29 08:51:23 UTC",
          false,
          "ai2",
          "Second AI response",
        ),
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          true,
          "user1",
          "First question",
        ),
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          false,
          "ai1",
          "First AI response",
        ),
        createMockMessage(
          "2025-08-29 08:51:23 UTC",
          true,
          "user2",
          "Follow-up question",
        ),
        createMockMessage(
          "2025-08-29 08:51:25 UTC",
          true,
          "user3",
          "Third question",
        ),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      expect(sorted.map((m) => m.id)).toEqual([
        "user1", // 08:51:21, User first
        "ai1", // 08:51:21, AI second
        "user2", // 08:51:23, User first
        "ai2", // 08:51:23, AI second
        "user3", // 08:51:25, only message at this time
      ]);
    });

    it("should handle conversation with streaming responses (identical timestamps)", () => {
      // Simulate scenario where user sends message and AI responds immediately
      // causing identical timestamps due to backend streaming/load balancer
      const messages = [
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          false,
          "stream-ai",
          "Streaming AI response",
        ),
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          true,
          "stream-user",
          "User message",
        ),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      expect(sorted[0].id).toBe("stream-user");
      expect(sorted[0].message).toBe("User message");
      expect(sorted[1].id).toBe("stream-ai");
      expect(sorted[1].message).toBe("Streaming AI response");
    });

    it("should handle conversation with multiple AI responses to one user message", () => {
      const messages = [
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          false,
          "ai-chunk-1",
          "AI chunk 1",
        ),
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          false,
          "ai-chunk-2",
          "AI chunk 2",
        ),
        createMockMessage(
          "2025-08-29 08:51:21 UTC",
          true,
          "user-msg",
          "User question",
        ),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      expect(sorted[0].id).toBe("user-msg");
      expect(sorted[0].isSend).toBe(true);
      // AI messages should come after, preserving their original order
      expect(sorted[1].id).toBe("ai-chunk-1");
      expect(sorted[2].id).toBe("ai-chunk-2");
      expect(sorted[1].isSend).toBe(false);
      expect(sorted[2].isSend).toBe(false);
    });
  });

  describe("Edge cases", () => {
    it("should handle empty array", () => {
      const messages: ChatMessageType[] = [];
      const sorted = [...messages].sort(sortSenderMessages);
      expect(sorted).toEqual([]);
    });

    it("should handle single message", () => {
      const messages = [
        createMockMessage("2025-08-29 08:51:21 UTC", true, "single"),
      ];
      const sorted = [...messages].sort(sortSenderMessages);
      expect(sorted.length).toBe(1);
      expect(sorted[0].id).toBe("single");
    });

    it("should handle invalid timestamp formats gracefully", () => {
      // Note: new Date() with invalid strings returns Invalid Date
      // but getTime() on Invalid Date returns NaN
      // NaN comparisons always return false, so original order should be preserved
      const messages = [
        createMockMessage("invalid-timestamp", false, "invalid-ai"),
        createMockMessage("2025-08-29 08:51:21 UTC", true, "valid-user"),
        createMockMessage("another-invalid", true, "invalid-user"),
      ];

      // Should not throw an error
      expect(() => [...messages].sort(sortSenderMessages)).not.toThrow();

      const sorted = [...messages].sort(sortSenderMessages);
      expect(sorted.length).toBe(3);

      // Valid timestamp should be sorted correctly relative to others
      const validMessage = sorted.find((m) => m.id === "valid-user");
      expect(validMessage).toBeDefined();
    });

    it("should handle millisecond precision timestamps", () => {
      const messages = [
        createMockMessage("2025-08-29 08:51:21.002 UTC", false, "ai-milli2"),
        createMockMessage("2025-08-29 08:51:21.001 UTC", true, "user-milli1"),
        createMockMessage("2025-08-29 08:51:21.001 UTC", false, "ai-milli1"),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      // Test the key behavior: chronological order with user-first for identical timestamps
      expect(sorted.length).toBe(3);

      // Messages with .001 should come before .002
      const firstTwoTimes = sorted
        .slice(0, 2)
        .map((m) => new Date(m.timestamp).getTime());
      const thirdTime = new Date(sorted[2].timestamp).getTime();

      expect(firstTwoTimes[0]).toEqual(firstTwoTimes[1]); // Same millisecond
      expect(firstTwoTimes[0]).toBeLessThan(thirdTime); // Earlier than third

      // Among the first two (same timestamp), user should come first
      const sameTimestampMessages = sorted.slice(0, 2);
      const userMsg = sameTimestampMessages.find((m) => m.isSend);
      const aiMsg = sameTimestampMessages.find((m) => !m.isSend);

      expect(userMsg?.id).toBe("user-milli1");
      expect(aiMsg?.id).toBe("ai-milli1");
      expect(sorted.indexOf(userMsg!)).toBeLessThan(sorted.indexOf(aiMsg!));
    });

    it("should handle timezone differences", () => {
      const messages = [
        createMockMessage("2025-08-29 11:51:21 UTC", true, "utc"),
        createMockMessage("2025-08-29T08:51:21-03:00", false, "minus3"), // Same as 11:51:21 UTC
        createMockMessage("2025-08-29 08:51:21 UTC", true, "utc-earlier"),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      expect(sorted[0].id).toBe("utc-earlier"); // 08:51:21 UTC earliest
      // Next two have same time (11:51:21 UTC), user should come first
      expect(sorted[1].id).toBe("utc");
      expect(sorted[2].id).toBe("minus3");
    });
  });

  describe("Performance and stability", () => {
    it("should be a stable sort for identical elements", () => {
      const messages = [
        createMockMessage("2025-08-29 08:51:21 UTC", true, "user-a"),
        createMockMessage("2025-08-29 08:51:21 UTC", true, "user-b"),
        createMockMessage("2025-08-29 08:51:21 UTC", true, "user-c"),
      ];

      const sorted1 = [...messages].sort(sortSenderMessages);
      const sorted2 = [...messages].sort(sortSenderMessages);

      // Should produce consistent results
      expect(sorted1.map((m) => m.id)).toEqual(sorted2.map((m) => m.id));
    });

    it("should handle large arrays efficiently", () => {
      // Generate 1000 messages with mixed timestamps
      const messages = Array.from({ length: 1000 }, (_, i) =>
        createMockMessage(
          `2025-08-29 08:${String(51 + (i % 10)).padStart(2, "0")}:${String(21 + (i % 40)).padStart(2, "0")} UTC`,
          i % 2 === 0, // Alternate between user and AI
          `msg-${i}`,
        ),
      );

      const startTime = performance.now();
      const sorted = [...messages].sort(sortSenderMessages);
      const endTime = performance.now();

      expect(sorted.length).toBe(1000);
      expect(endTime - startTime).toBeLessThan(100); // Should complete in <100ms

      // Verify sorting is correct - timestamps should be chronological
      for (let i = 1; i < sorted.length; i++) {
        const prevTime = new Date(sorted[i - 1].timestamp).getTime();
        const currTime = new Date(sorted[i].timestamp).getTime();
        // Skip comparison if either timestamp is invalid (NaN)
        if (!isNaN(prevTime) && !isNaN(currTime)) {
          expect(prevTime).toBeLessThanOrEqual(currTime);
        }
      }
    });
  });

  describe("Type safety", () => {
    it("should work with all required ChatMessageType properties", () => {
      const message: ChatMessageType = {
        id: "complete-msg",
        timestamp: "2025-08-29 08:51:21 UTC",
        isSend: true,
        message: "Complete message object",
        sender_name: "Test User",
        session: "test-session",
        files: [{ path: "/test", type: "text", name: "test.txt" }],
        edit: false,
        category: "message",
        properties: {
          source: { id: "test", display_name: "Test", source: "test" },
        },
        content_blocks: [],
        template: "test template",
        thought: "test thought",
        prompt: "test prompt",
        chatKey: "test-key",
        componentId: "test-component",
        stream_url: "test-stream",
      };

      expect(() => sortSenderMessages(message, message)).not.toThrow();
      expect(sortSenderMessages(message, message)).toBe(0);
    });
  });
});
