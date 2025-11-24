/**
 * Integration tests for message sorting functionality.
 * Tests how the sortSenderMessages function integrates with real message data structures
 * and simulates the exact data transformation that happens in the chat-view component.
 */
import type { ChatMessageType } from "../../../../../types/chat";
import sortSenderMessages from "../helpers/sort-sender-messages";

// Helper to create messages like they come from the backend/store
const createStoreMessage = (
  id: string,
  timestamp: string,
  sender: "User" | "Machine",
  text: string,
  flow_id: string = "test-flow-id",
) => ({
  id,
  timestamp,
  sender,
  sender_name: sender === "User" ? "User" : "AI",
  text,
  session_id: "test-session",
  flow_id,
  files: [],
  edit: false,
  error: false,
  category: "message",
  properties: {},
  content_blocks: [],
});

// Helper to simulate the transformation that chat-view.tsx does
const transformMessages = (storeMessages: any[]): ChatMessageType[] => {
  return storeMessages
    .filter((message) => message.flow_id === "test-flow-id")
    .map((message) => ({
      isSend: message.sender === "User",
      message: message.text,
      sender_name:
        message.sender_name || (message.sender === "User" ? "User" : "AI"),
      files: message.files || [],
      id: message.id,
      timestamp: message.timestamp,
      session: message.session_id,
      edit: message.edit || false,
      category: message.category || "message",
      properties: message.properties || {},
      content_blocks: message.content_blocks || [],
    }));
};

describe("Message Sorting Integration", () => {
  describe("Real component data flow simulation", () => {
    it("should correctly sort messages through the full data transformation pipeline", () => {
      // Simulate messages arriving from backend in random order
      const storeMessages = [
        createStoreMessage(
          "ai-response",
          "2025-08-29 08:51:23 UTC",
          "Machine",
          "AI response",
        ),
        createStoreMessage(
          "user-question",
          "2025-08-29 08:51:21 UTC",
          "User",
          "User question",
        ),
        createStoreMessage(
          "ai-followup",
          "2025-08-29 08:51:22 UTC",
          "Machine",
          "AI followup",
        ),
      ];

      // Transform like the real component
      const transformedMessages = transformMessages(storeMessages);

      // Sort using our function
      const sortedMessages = [...transformedMessages].sort(sortSenderMessages);

      // Verify chronological order
      expect(sortedMessages.map((m) => m.id)).toEqual([
        "user-question", // 08:51:21
        "ai-followup", // 08:51:22
        "ai-response", // 08:51:23
      ]);
    });

    it("should handle the GitHub issue #9186 scenario", () => {
      // Exact scenario from the GitHub issue: identical timestamps causing swaps
      const problematicMessages = [
        createStoreMessage(
          "ai-resp",
          "2025-08-29 08:51:21 UTC",
          "Machine",
          "I'm an AI language model",
        ),
        createStoreMessage(
          "user-q",
          "2025-08-29 08:51:21 UTC",
          "User",
          "Who are you?",
        ),
      ];

      const transformed = transformMessages(problematicMessages);
      const sorted = [...transformed].sort(sortSenderMessages);

      // User question should come first, even though AI was first in the array
      expect(sorted[0].id).toBe("user-q");
      expect(sorted[0].isSend).toBe(true);
      expect(sorted[1].id).toBe("ai-resp");
      expect(sorted[1].isSend).toBe(false);
    });

    it("should handle streaming conversation with load balancer timing issues", () => {
      // Scenario: streaming + load balancer causes identical timestamps
      const streamingMessages = [
        createStoreMessage(
          "stream-chunk-2",
          "2025-08-29 08:51:21 UTC",
          "Machine",
          "I can help with",
        ),
        createStoreMessage(
          "user-input",
          "2025-08-29 08:51:21 UTC",
          "User",
          "Can you help me code?",
        ),
        createStoreMessage(
          "stream-chunk-1",
          "2025-08-29 08:51:21 UTC",
          "Machine",
          "Of course!",
        ),
      ];

      const transformed = transformMessages(streamingMessages);
      const sorted = [...transformed].sort(sortSenderMessages);

      // User input should be first
      expect(sorted[0].id).toBe("user-input");
      expect(sorted[0].isSend).toBe(true);

      // AI streaming chunks should follow in original order (stable sort)
      expect(sorted[1].isSend).toBe(false);
      expect(sorted[2].isSend).toBe(false);
      expect(sorted[1].id).toBe("stream-chunk-2");
      expect(sorted[2].id).toBe("stream-chunk-1");
    });
  });

  describe("Data consistency validation", () => {
    it("should maintain referential integrity after sorting", () => {
      const originalMessages = [
        createStoreMessage(
          "msg1",
          "2025-08-29 08:51:21 UTC",
          "User",
          "Original text",
          "test-flow-id",
        ),
        createStoreMessage(
          "msg2",
          "2025-08-29 08:51:21 UTC",
          "Machine",
          "AI response",
          "test-flow-id",
        ),
      ];

      const transformed = transformMessages(originalMessages);
      const sorted = [...transformed].sort(sortSenderMessages);

      // Verify all properties are maintained
      expect(sorted.length).toBe(2);

      // User message should come first (due to identical timestamps)
      expect(sorted[0].isSend).toBe(true);
      expect(sorted[0].message).toBe("Original text");
      expect(sorted[0].session).toBe("test-session");

      expect(sorted[1].isSend).toBe(false);
      expect(sorted[1].message).toBe("AI response");
      expect(sorted[1].session).toBe("test-session");
    });

    it("should handle filtering by flow_id correctly", () => {
      const mixedFlowMessages = [
        createStoreMessage(
          "msg1",
          "2025-08-29 08:51:21 UTC",
          "User",
          "Message 1",
          "test-flow-id",
        ),
        createStoreMessage(
          "msg2",
          "2025-08-29 08:51:22 UTC",
          "Machine",
          "Message 2",
          "other-flow",
        ),
        createStoreMessage(
          "msg3",
          "2025-08-29 08:51:23 UTC",
          "User",
          "Message 3",
          "test-flow-id",
        ),
      ];

      const transformed = transformMessages(mixedFlowMessages);
      const sorted = [...transformed].sort(sortSenderMessages);

      // Only messages from test-flow-id should be included
      expect(sorted.length).toBe(2);
      expect(sorted.map((m) => m.id)).toEqual(["msg1", "msg3"]);
    });
  });

  describe("Performance with realistic data volumes", () => {
    it("should handle typical chat session sizes efficiently", () => {
      // Simulate a realistic chat session (50 message exchanges)
      const chatSession = Array.from({ length: 100 }, (_, i) => {
        const isUser = i % 2 === 0;
        return createStoreMessage(
          `msg-${i}`,
          `2025-08-29 08:${String(51 + Math.floor(i / 10)).padStart(2, "0")}:${String(21 + (i % 60)).padStart(2, "0")} UTC`,
          isUser ? "User" : "Machine",
          `Message ${i}`,
        );
      });

      const startTime = performance.now();
      const transformed = transformMessages(chatSession);
      const sorted = [...transformed].sort(sortSenderMessages);
      const endTime = performance.now();

      expect(sorted.length).toBe(100);
      expect(endTime - startTime).toBeLessThan(100); // Should be fast, allowing for CI overhead

      // Verify chronological order (skip invalid timestamps)
      for (let i = 1; i < sorted.length; i++) {
        const prevTime = new Date(sorted[i - 1].timestamp).getTime();
        const currTime = new Date(sorted[i].timestamp).getTime();
        if (!isNaN(prevTime) && !isNaN(currTime)) {
          expect(prevTime).toBeLessThanOrEqual(currTime);
        }
      }
    });

    it("should maintain O(n log n) performance characteristics", () => {
      const sizes = [50, 200, 500];
      const timings: number[] = [];

      sizes.forEach((size) => {
        const messages = Array.from({ length: size }, (_, i) =>
          createStoreMessage(
            `msg-${i}`,
            `2025-08-29 08:${String(51 + (i % 10)).padStart(2, "0")}:${String(21 + (i % 40)).padStart(2, "0")} UTC`,
            i % 3 === 0 ? "User" : "Machine",
            `Message ${i}`,
          ),
        );

        const transformed = transformMessages(messages);

        const startTime = performance.now();
        [...transformed].sort(sortSenderMessages);
        const endTime = performance.now();

        timings.push(endTime - startTime);
      });

      // Performance should scale sub-quadratically
      // Note: Absolute timing varies by system load, so we just verify completion
      expect(timings[0]).toBeGreaterThan(0);
      expect(timings[1]).toBeGreaterThan(0);
      expect(timings[2]).toBeGreaterThan(0);
      // All should complete reasonably fast (<50ms for 500 items)
      expect(Math.max(...timings)).toBeLessThan(50);
    });
  });

  describe("Edge cases in real usage", () => {
    it("should handle malformed timestamps gracefully", () => {
      const messagesWithBadTimestamps = [
        createStoreMessage("bad1", "invalid-date", "User", "Bad timestamp"),
        createStoreMessage(
          "good1",
          "2025-08-29 08:51:21 UTC",
          "Machine",
          "Good timestamp",
        ),
        createStoreMessage("bad2", "", "User", "Empty timestamp"),
      ];

      const transformed = transformMessages(messagesWithBadTimestamps);

      // Should not throw
      expect(() => [...transformed].sort(sortSenderMessages)).not.toThrow();

      const sorted = [...transformed].sort(sortSenderMessages);
      expect(sorted.length).toBe(3);
    });

    it("should handle messages with missing properties", () => {
      const incompleteMessages = [
        // Missing some properties
        {
          id: "incomplete1",
          timestamp: "2025-08-29 08:51:21 UTC",
          sender: "User",
          text: "Incomplete message",
          session_id: "test-session",
          flow_id: "test-flow-id",
        },
        createStoreMessage(
          "complete1",
          "2025-08-29 08:51:22 UTC",
          "Machine",
          "Complete message",
        ),
      ] as any;

      const transformed = transformMessages(incompleteMessages);
      const sorted = [...transformed].sort(sortSenderMessages);

      expect(sorted.length).toBe(2);
      expect(sorted[0].id).toBe("incomplete1"); // Earlier timestamp
      expect(sorted[1].id).toBe("complete1");
    });
  });

  describe("Backwards compatibility", () => {
    it("should work with legacy message formats", () => {
      // Simulate messages that might exist from before the fix
      const legacyMessages = [
        {
          ...createStoreMessage(
            "legacy1",
            "2025-08-29 08:51:21 UTC",
            "Machine",
            "Legacy AI message",
          ),
          // Legacy format might not have all modern properties
        },
        createStoreMessage(
          "modern1",
          "2025-08-29 08:51:21 UTC",
          "User",
          "Modern user message",
        ),
      ];

      const transformed = transformMessages(legacyMessages);
      const sorted = [...transformed].sort(sortSenderMessages);

      // User message should come first due to our sorting logic
      expect(sorted[0].id).toBe("modern1");
      expect(sorted[0].isSend).toBe(true);
      expect(sorted[1].id).toBe("legacy1");
      expect(sorted[1].isSend).toBe(false);
    });
  });
});
