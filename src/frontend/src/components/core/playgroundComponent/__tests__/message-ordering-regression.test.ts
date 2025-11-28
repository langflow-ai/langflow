import type { ChatMessageType } from "../../../../../types/chat";
import sortSenderMessages from "../helpers/sort-sender-messages";

/**
 * Regression tests for GitHub issue #9186: Chat history ordering problem
 *
 * These tests specifically validate the scenarios that were causing
 * message ordering issues in production.
 */

// Helper function to create mock ChatMessageType matching real data structure
const createMessage = (
  id: string,
  timestamp: string,
  isSend: boolean,
  message: string = "test message",
): ChatMessageType => ({
  id,
  timestamp,
  isSend,
  message,
  sender_name: isSend ? "User" : "AI",
  session: "session-test",
  files: [],
  edit: false,
  category: "message",
  properties: {
    source: { id: "test", display_name: "Test", source: "test" },
  },
  content_blocks: [],
});

describe("Message Ordering Regression Tests - GitHub Issue #9186", () => {
  describe("Production scenarios that caused ordering issues", () => {
    it("should handle identical timestamps from PostgreSQL with second precision", () => {
      // Real scenario: PostgreSQL storing timestamps with second precision
      // Frontend generates UTC+0, backend was UTC+3, causing identical second-level timestamps
      const messages = [
        createMessage(
          "ai-response",
          "2025-08-29 08:51:21 UTC",
          false,
          "I'm an AI language model",
        ),
        createMessage(
          "user-question",
          "2025-08-29 08:51:21 UTC",
          true,
          "Who are you?",
        ),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      // User question should come first, even though AI response was added to array first
      expect(sorted[0].id).toBe("user-question");
      expect(sorted[0].isSend).toBe(true);
      expect(sorted[1].id).toBe("ai-response");
      expect(sorted[1].isSend).toBe(false);
    });

    it("should handle streaming responses with load balancer timing", () => {
      // Scenario: Load balancer + streaming causing multiple messages with same timestamp
      const messages = [
        createMessage(
          "stream-chunk-2",
          "2025-08-29 08:51:21 UTC",
          false,
          "models currently",
        ),
        createMessage(
          "user-input",
          "2025-08-29 08:51:21 UTC",
          true,
          "what models do you support?",
        ),
        createMessage(
          "stream-chunk-1",
          "2025-08-29 08:51:21 UTC",
          false,
          "It seems there are various",
        ),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      // User input should be first
      expect(sorted[0].id).toBe("user-input");
      expect(sorted[0].isSend).toBe(true);

      // AI streaming chunks should follow, maintaining their relative order
      expect(sorted[1].isSend).toBe(false);
      expect(sorted[2].isSend).toBe(false);
      expect(sorted[1].id).toBe("stream-chunk-2"); // Original order preserved for same type
      expect(sorted[2].id).toBe("stream-chunk-1");
    });

    it("should handle rapid-fire user questions with immediate AI responses", () => {
      // Scenario: User sends multiple questions quickly, AI responds immediately
      // Backend processing causes timestamp collisions
      const messages = [
        createMessage(
          "ai-2",
          "2025-08-29 08:51:22 UTC",
          false,
          "Second AI response",
        ),
        createMessage(
          "user-2",
          "2025-08-29 08:51:22 UTC",
          true,
          "Second question",
        ),
        createMessage(
          "ai-1",
          "2025-08-29 08:51:21 UTC",
          false,
          "First AI response",
        ),
        createMessage(
          "user-1",
          "2025-08-29 08:51:21 UTC",
          true,
          "First question",
        ),
        createMessage(
          "ai-3",
          "2025-08-29 08:51:23 UTC",
          false,
          "Third AI response",
        ),
        createMessage(
          "user-3",
          "2025-08-29 08:51:23 UTC",
          true,
          "Third question",
        ),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      // Expected chronological order: User → AI → User → AI → User → AI
      const expectedOrder = [
        "user-1",
        "ai-1",
        "user-2",
        "ai-2",
        "user-3",
        "ai-3",
      ];
      expect(sorted.map((m) => m.id)).toEqual(expectedOrder);

      // Verify conversation flow pattern
      for (let i = 0; i < sorted.length; i += 2) {
        expect(sorted[i].isSend).toBe(true); // User message
        if (i + 1 < sorted.length) {
          expect(sorted[i + 1].isSend).toBe(false); // AI response
        }
      }
    });

    it("should handle timezone discrepancy scenarios", () => {
      // Original issue: Frontend UTC+0, Backend UTC+3, Database UTC+3 → UTC+0
      // Messages generated at "same time" but with different timezone representations
      const messages = [
        createMessage(
          "ai-utc",
          "2025-08-29 08:51:21 UTC",
          false,
          "AI response in UTC",
        ),
        createMessage(
          "user-utc",
          "2025-08-29 08:51:21 UTC",
          true,
          "User message in UTC",
        ),
        // These represent the same moment in time but different timezone formats
        createMessage(
          "ai-iso",
          "2025-08-29T08:51:21Z",
          false,
          "AI response ISO",
        ),
        createMessage(
          "user-iso",
          "2025-08-29T08:51:21Z",
          true,
          "User message ISO",
        ),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      // Should group by actual timestamp, with users first in each group
      // All four messages have the same timestamp, so users should come first
      expect(sorted[0].isSend).toBe(true); // user-utc
      expect(sorted[1].isSend).toBe(true); // user-iso (also user, same timestamp)
      expect(sorted[2].isSend).toBe(false); // ai-utc
      expect(sorted[3].isSend).toBe(false); // ai-iso
    });
  });

  describe("Backend streaming edge cases", () => {
    it("should handle Agent component message generation", () => {
      // Agent component generates messages with sender="Machine" and different names
      const messages = [
        createMessage(
          "agent-step-2",
          "2025-08-29 08:51:21 UTC",
          false,
          "Agent processing step 2",
        ),
        createMessage(
          "user-query",
          "2025-08-29 08:51:21 UTC",
          true,
          "Process this request",
        ),
        createMessage(
          "agent-step-1",
          "2025-08-29 08:51:21 UTC",
          false,
          "Agent processing step 1",
        ),
        createMessage(
          "agent-result",
          "2025-08-29 08:51:21 UTC",
          false,
          "Agent final result",
        ),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      // User query should be first
      expect(sorted[0].id).toBe("user-query");
      expect(sorted[0].isSend).toBe(true);

      // Agent messages should follow in original order (stable sort)
      const agentMessages = sorted.slice(1);
      expect(agentMessages.every((m) => !m.isSend)).toBe(true);
      expect(agentMessages.map((m) => m.id)).toEqual([
        "agent-step-2",
        "agent-step-1",
        "agent-result",
      ]);
    });

    it("should handle message updates during streaming", () => {
      // Messages might be updated in place during streaming, causing re-sorts
      const messages = [
        createMessage(
          "stream-final",
          "2025-08-29 08:51:21 UTC",
          false,
          "Complete response",
        ),
        createMessage(
          "user-msg",
          "2025-08-29 08:51:21 UTC",
          true,
          "User message",
        ),
        createMessage(
          "stream-partial",
          "2025-08-29 08:51:21 UTC",
          false,
          "Partial resp...",
        ),
      ];

      // Multiple sorts should be stable
      const sorted1 = [...messages].sort(sortSenderMessages);
      const sorted2 = [...messages].sort(sortSenderMessages);

      expect(sorted1.map((m) => m.id)).toEqual(sorted2.map((m) => m.id));

      // User message should consistently be first
      expect(sorted1[0].id).toBe("user-msg");
      expect(sorted2[0].id).toBe("user-msg");
    });
  });

  describe("Database precision and rounding", () => {
    it("should handle database timestamp rounding", () => {
      // Database might round timestamps, causing apparent simultaneity
      const messages = [
        createMessage("msg-1", "2025-08-29 08:51:21.999 UTC", false),
        createMessage("msg-2", "2025-08-29 08:51:21.001 UTC", true),
        createMessage("msg-3", "2025-08-29 08:51:21.500 UTC", false),
      ];

      const sorted = [...messages].sort(sortSenderMessages);

      // Should sort by actual timestamp precision
      expect(sorted[0].id).toBe("msg-2"); // .001
      expect(sorted[1].id).toBe("msg-3"); // .500
      expect(sorted[2].id).toBe("msg-1"); // .999
    });

    it("should handle microsecond precision loss", () => {
      // Original timestamps have microseconds, but database stores only seconds
      const originalMessages = [
        {
          timestamp: "2025-08-29 08:51:21.123456 UTC",
          isSend: false,
          id: "ai-micro",
        },
        {
          timestamp: "2025-08-29 08:51:21.123456 UTC",
          isSend: true,
          id: "user-micro",
        },
      ];

      // After database round-trip, microseconds are lost
      const dbMessages = originalMessages.map((m) =>
        createMessage(m.id, "2025-08-29 08:51:21 UTC", m.isSend),
      );

      const sorted = dbMessages.sort(sortSenderMessages);

      // User should still come first despite identical timestamps
      expect(sorted[0].id).toBe("user-micro");
      expect(sorted[1].id).toBe("ai-micro");
    });
  });

  describe("Real conversation patterns", () => {
    it("should handle typical question-answer flow", () => {
      // Realistic conversation with multiple exchanges
      const conversation = [
        // Third exchange (out of order in array)
        createMessage(
          "ai-3",
          "2025-08-29 08:51:25 UTC",
          false,
          "Python is great for beginners because...",
        ),
        createMessage(
          "user-3",
          "2025-08-29 08:51:25 UTC",
          true,
          "What programming language should I learn?",
        ),

        // First exchange
        createMessage(
          "ai-1",
          "2025-08-29 08:51:21 UTC",
          false,
          "Hello! I'm an AI assistant. How can I help you?",
        ),
        createMessage("user-1", "2025-08-29 08:51:21 UTC", true, "Hello"),

        // Second exchange
        createMessage(
          "user-2",
          "2025-08-29 08:51:23 UTC",
          true,
          "Can you help me with coding?",
        ),
        createMessage(
          "ai-2",
          "2025-08-29 08:51:23 UTC",
          false,
          "Absolutely! I'd be happy to help you with coding.",
        ),
      ];

      const sorted = conversation.sort(sortSenderMessages);

      // Should create natural conversation flow
      const expectedFlow = [
        { id: "user-1", type: "question" },
        { id: "ai-1", type: "answer" },
        { id: "user-2", type: "question" },
        { id: "ai-2", type: "answer" },
        { id: "user-3", type: "question" },
        { id: "ai-3", type: "answer" },
      ];

      expectedFlow.forEach((expected, index) => {
        expect(sorted[index].id).toBe(expected.id);
        expect(sorted[index].isSend).toBe(expected.type === "question");
      });
    });

    it("should handle error messages and system messages", () => {
      // Mix of user messages, AI responses, and system errors
      const messages = [
        createMessage(
          "error-msg",
          "2025-08-29 08:51:21 UTC",
          false,
          "Error: Connection timeout",
        ),
        createMessage(
          "user-retry",
          "2025-08-29 08:51:21 UTC",
          true,
          "Can you try again?",
        ),
        createMessage(
          "user-original",
          "2025-08-29 08:51:21 UTC",
          true,
          "What's the weather?",
        ),
        createMessage(
          "ai-response",
          "2025-08-29 08:51:21 UTC",
          false,
          "I don't have access to weather data",
        ),
      ];

      const sorted = messages.sort(sortSenderMessages);

      // User messages should come first, maintaining their relative order
      expect(sorted[0].isSend).toBe(true);
      expect(sorted[1].isSend).toBe(true);
      expect(sorted[2].isSend).toBe(false);
      expect(sorted[3].isSend).toBe(false);

      // Verify relative order within same sender type is preserved
      expect(sorted[0].id).toBe("user-retry"); // First user message in array
      expect(sorted[1].id).toBe("user-original"); // Second user message in array
    });
  });

  describe("Performance regression tests", () => {
    it("should maintain O(n log n) performance characteristics", () => {
      const sizes = [10, 100, 1000];
      const timings: number[] = [];

      sizes.forEach((size) => {
        const messages = Array.from({ length: size }, (_, i) =>
          createMessage(
            `msg-${i}`,
            `2025-08-29 08:${String(51 + (i % 10)).padStart(2, "0")}:${String(21 + (i % 60)).padStart(2, "0")} UTC`,
            i % 3 === 0, // Mix of user and AI messages
          ),
        );

        const startTime = performance.now();
        [...messages].sort(sortSenderMessages);
        const endTime = performance.now();

        timings.push(endTime - startTime);
      });

      // Verify performance scales reasonably (not exponentially)
      // Each 10x increase in size should not cause 100x increase in time
      expect(timings[1]).toBeLessThan(timings[0] * 50); // 100 items vs 10 items
      expect(timings[2]).toBeLessThan(timings[1] * 50); // 1000 items vs 100 items
    });

    it("should handle worst-case scenario: all messages have identical timestamps", () => {
      // Stress test: 500 messages all with same timestamp
      const messages = Array.from({ length: 500 }, (_, i) =>
        createMessage(
          `msg-${i}`,
          "2025-08-29 08:51:21 UTC", // Same timestamp for all
          i % 2 === 0,
        ),
      );

      const startTime = performance.now();
      const sorted = [...messages].sort(sortSenderMessages);
      const endTime = performance.now();

      expect(endTime - startTime).toBeLessThan(50); // Should complete in <50ms
      expect(sorted.length).toBe(500);

      // All user messages should come before all AI messages
      const userCount = sorted.filter((m) => m.isSend).length;

      // First userCount messages should be users, rest should be AI
      for (let i = 0; i < userCount; i++) {
        expect(sorted[i].isSend).toBe(true);
      }
      for (let i = userCount; i < sorted.length; i++) {
        expect(sorted[i].isSend).toBe(false);
      }
    });
  });

  describe("Backwards compatibility", () => {
    it("should maintain sort stability for pre-fix messages", () => {
      // Messages that would have been affected by the original bug
      const legacyMessages = [
        createMessage(
          "legacy-ai",
          "2025-08-29 08:50:23 UTC",
          false,
          "Code: None",
        ),
        createMessage(
          "legacy-user",
          "2025-08-29 08:50:24 UTC",
          true,
          "Who are you?",
        ),
      ];

      const sorted = legacyMessages.sort(sortSenderMessages);

      // These should still sort correctly by timestamp
      expect(sorted[0].id).toBe("legacy-ai"); // Earlier timestamp
      expect(sorted[1].id).toBe("legacy-user"); // Later timestamp
    });
  });
});
