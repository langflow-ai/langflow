import { act, renderHook } from "@testing-library/react";
import type { Message } from "../../types/messages";
import { useMessagesStore } from "../messagesStore";

const mockMessage: Message = {
  id: "msg-1",
  text: "Hello world",
  sender: "User",
  sender_name: "Test User",
  session_id: "session-1",
  timestamp: "2023-01-01T00:00:00Z",
  files: [],
  edit: false,
  background_color: "#ffffff",
  text_color: "#000000",
  flow_id: "flow-1",
};

const mockMachineMessage: Message = {
  id: "msg-2",
  text: "Machine response",
  sender: "Machine",
  sender_name: "AI Assistant",
  session_id: "session-1",
  timestamp: "2023-01-01T00:01:00Z",
  files: ["file1.txt"],
  edit: false,
  background_color: "#f0f0f0",
  text_color: "#333333",
  flow_id: "flow-1",
  category: "response",
  properties: { type: "ai" },
};

const mockMessage2: Message = {
  id: "msg-3",
  text: "Another message",
  sender: "User",
  sender_name: "Test User",
  session_id: "session-2",
  timestamp: "2023-01-01T00:02:00Z",
  files: [],
  edit: true,
  background_color: "#ffffff",
  text_color: "#000000",
  flow_id: "flow-2",
};

describe("useMessagesStore", () => {
  beforeEach(() => {
    useMessagesStore.getState().clearMessages();
    act(() => {
      useMessagesStore.setState({
        messages: [],
        displayLoadingMessage: false,
      });
    });
  });

  describe("initial state", () => {
    it("should have correct initial state", () => {
      const { result } = renderHook(() => useMessagesStore());

      expect(result.current.messages).toEqual([]);
      expect(result.current.displayLoadingMessage).toBe(false);
    });
  });

  describe("setMessages", () => {
    it("should set empty messages array", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([]);
      });

      expect(result.current.messages).toEqual([]);
    });

    it("should set single message", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      expect(result.current.messages).toEqual([mockMessage]);
    });

    it("should set multiple messages", () => {
      const { result } = renderHook(() => useMessagesStore());
      const messages = [mockMessage, mockMessage2];

      act(() => {
        result.current.setMessages(messages);
      });

      expect(result.current.messages).toEqual(messages);
    });

    it("should replace existing messages", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });
      expect(result.current.messages).toEqual([mockMessage]);

      act(() => {
        result.current.setMessages([mockMessage2]);
      });
      expect(result.current.messages).toEqual([mockMessage2]);
    });
  });

  describe("addMessage", () => {
    it("should add new message to empty list", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.addMessage(mockMessage);
      });

      expect(result.current.messages).toEqual([mockMessage]);
    });

    it("should add multiple messages", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.addMessage(mockMessage);
      });
      expect(result.current.messages).toHaveLength(1);

      act(() => {
        result.current.addMessage(mockMessage2);
      });
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages).toEqual([mockMessage, mockMessage2]);
    });

    it("should update existing message instead of adding duplicate", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.addMessage(mockMessage);
      });
      expect(result.current.messages).toHaveLength(1);

      const updatedMessage = { ...mockMessage, text: "Updated text" };
      act(() => {
        result.current.addMessage(updatedMessage);
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0].text).toBe("Updated text");
    });

    it("should set displayLoadingMessage to false when sender is Machine", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        useMessagesStore.setState({ displayLoadingMessage: true });
      });
      expect(result.current.displayLoadingMessage).toBe(true);

      act(() => {
        result.current.addMessage(mockMachineMessage);
      });

      expect(result.current.displayLoadingMessage).toBe(false);
    });

    it("should not change displayLoadingMessage when sender is not Machine", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        useMessagesStore.setState({ displayLoadingMessage: true });
      });
      expect(result.current.displayLoadingMessage).toBe(true);

      act(() => {
        result.current.addMessage(mockMessage);
      });

      expect(result.current.displayLoadingMessage).toBe(true);
    });

    it("should call updateMessagePartial for existing message", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.addMessage(mockMessage);
      });
      expect(result.current.messages[0].text).toBe("Hello world");

      const partialUpdate = { id: mockMessage.id, text: "Partial update" };
      act(() => {
        result.current.addMessage(partialUpdate as Message);
      });

      expect(result.current.messages[0].text).toBe("Partial update");
      expect(result.current.messages).toHaveLength(1);
    });
  });

  describe("removeMessage", () => {
    it("should remove existing message", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage, mockMessage2]);
      });
      expect(result.current.messages).toHaveLength(2);

      act(() => {
        result.current.removeMessage(mockMessage);
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0]).toEqual(mockMessage2);
    });

    it("should handle removing non-existent message", () => {
      const { result } = renderHook(() => useMessagesStore());
      const nonExistentMessage = { ...mockMessage, id: "non-existent" };

      act(() => {
        result.current.setMessages([mockMessage]);
      });
      expect(result.current.messages).toHaveLength(1);

      act(() => {
        result.current.removeMessage(nonExistentMessage);
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0]).toEqual(mockMessage);
    });

    it("should remove message from empty list without error", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.removeMessage(mockMessage);
      });

      expect(result.current.messages).toEqual([]);
    });
  });

  describe("updateMessage", () => {
    it("should update existing message", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage, mockMessage2]);
      });

      const updatedMessage = { ...mockMessage, text: "Updated text" };
      act(() => {
        result.current.updateMessage(updatedMessage);
      });

      expect(result.current.messages[0]).toEqual(updatedMessage);
      expect(result.current.messages[1]).toEqual(mockMessage2);
    });

    it("should handle updating non-existent message", () => {
      const { result } = renderHook(() => useMessagesStore());
      const nonExistentMessage = { ...mockMessage, id: "non-existent" };

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      act(() => {
        result.current.updateMessage(nonExistentMessage);
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0]).toEqual(mockMessage);
    });

    it("should replace entire message object", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      const completelyNewMessage = {
        ...mockMessage,
        text: "Completely new text",
        sender: "New Sender",
        background_color: "#ff0000",
      };

      act(() => {
        result.current.updateMessage(completelyNewMessage);
      });

      expect(result.current.messages[0]).toEqual(completelyNewMessage);
    });
  });

  describe("updateMessagePartial", () => {
    it("should partially update existing message", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage, mockMessage2]);
      });

      const partialUpdate = { id: mockMessage.id, text: "Partially updated" };
      act(() => {
        result.current.updateMessagePartial(partialUpdate);
      });

      expect(result.current.messages[0]).toEqual({
        ...mockMessage,
        text: "Partially updated",
      });
      expect(result.current.messages[1]).toEqual(mockMessage2);
    });

    it("should update multiple fields partially", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      const partialUpdate = {
        id: mockMessage.id,
        text: "New text",
        background_color: "#ff0000",
      };

      act(() => {
        result.current.updateMessagePartial(partialUpdate);
      });

      expect(result.current.messages[0]).toEqual({
        ...mockMessage,
        text: "New text",
        background_color: "#ff0000",
      });
    });

    it("should handle updating non-existent message", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      const partialUpdate = { id: "non-existent", text: "Should not update" };
      act(() => {
        result.current.updateMessagePartial(partialUpdate);
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0]).toEqual(mockMessage);
    });

    it("should find message efficiently by searching backwards", () => {
      const { result } = renderHook(() => useMessagesStore());
      const messages = Array.from({ length: 100 }, (_, i) => ({
        ...mockMessage,
        id: `msg-${i}`,
        text: `Message ${i}`,
      }));

      act(() => {
        result.current.setMessages(messages);
      });

      const lastMessageUpdate = { id: "msg-99", text: "Updated last message" };
      act(() => {
        result.current.updateMessagePartial(lastMessageUpdate);
      });

      expect(result.current.messages[99].text).toBe("Updated last message");
    });
  });

  describe("updateMessageText", () => {
    it("should append chunk to message text", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      act(() => {
        result.current.updateMessageText(mockMessage.id, " - appended");
      });

      expect(result.current.messages[0].text).toBe("Hello world - appended");
    });

    it("should append multiple chunks", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      act(() => {
        result.current.updateMessageText(mockMessage.id, " - first");
      });
      expect(result.current.messages[0].text).toBe("Hello world - first");

      act(() => {
        result.current.updateMessageText(mockMessage.id, " - second");
      });
      expect(result.current.messages[0].text).toBe(
        "Hello world - first - second",
      );
    });

    it("should handle updating non-existent message", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      act(() => {
        result.current.updateMessageText(
          "non-existent",
          " - should not update",
        );
      });

      expect(result.current.messages[0].text).toBe("Hello world");
    });

    it("should find message efficiently by searching backwards", () => {
      const { result } = renderHook(() => useMessagesStore());
      const messages = Array.from({ length: 100 }, (_, i) => ({
        ...mockMessage,
        id: `msg-${i}`,
        text: `Message ${i}`,
      }));

      act(() => {
        result.current.setMessages(messages);
      });

      act(() => {
        result.current.updateMessageText("msg-99", " - updated");
      });

      expect(result.current.messages[99].text).toBe("Message 99 - updated");
    });

    it("should handle empty chunk", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      act(() => {
        result.current.updateMessageText(mockMessage.id, "");
      });

      expect(result.current.messages[0].text).toBe("Hello world");
    });
  });

  describe("clearMessages", () => {
    it("should clear all messages", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage, mockMessage2]);
      });
      expect(result.current.messages).toHaveLength(2);

      act(() => {
        result.current.clearMessages();
      });

      expect(result.current.messages).toEqual([]);
    });

    it("should clear messages from empty list without error", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.clearMessages();
      });

      expect(result.current.messages).toEqual([]);
    });

    it("should not affect displayLoadingMessage", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        useMessagesStore.setState({ displayLoadingMessage: true });
        result.current.setMessages([mockMessage]);
      });

      act(() => {
        result.current.clearMessages();
      });

      expect(result.current.messages).toEqual([]);
      expect(result.current.displayLoadingMessage).toBe(true);
    });
  });

  describe("removeMessages", () => {
    it("should remove messages by IDs", async () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([
          mockMessage,
          mockMachineMessage,
          mockMessage2,
        ]);
      });
      expect(result.current.messages).toHaveLength(3);

      let removedMessages;
      await act(async () => {
        removedMessages = await result.current.removeMessages([
          mockMessage.id,
          mockMessage2.id,
        ]);
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0]).toEqual(mockMachineMessage);
      expect(removedMessages).toHaveLength(1);
      expect(removedMessages[0]).toEqual(mockMachineMessage);
    });

    it("should handle removing non-existent IDs", async () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      let removedMessages;
      await act(async () => {
        removedMessages = await result.current.removeMessages([
          "non-existent-1",
          "non-existent-2",
        ]);
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0]).toEqual(mockMessage);
      expect(removedMessages).toHaveLength(1);
      expect(removedMessages[0]).toEqual(mockMessage);
    });

    it("should remove all messages if all IDs match", async () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage, mockMessage2]);
      });

      let removedMessages;
      await act(async () => {
        removedMessages = await result.current.removeMessages([
          mockMessage.id,
          mockMessage2.id,
        ]);
      });

      expect(result.current.messages).toEqual([]);
      expect(removedMessages).toEqual([]);
    });

    it("should handle empty IDs array", async () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage, mockMessage2]);
      });

      let removedMessages;
      await act(async () => {
        removedMessages = await result.current.removeMessages([]);
      });

      expect(result.current.messages).toHaveLength(2);
      expect(removedMessages).toHaveLength(2);
    });

    it("should return promise that resolves with remaining messages", async () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage, mockMessage2]);
      });

      let removedMessages;
      await act(async () => {
        removedMessages = await result.current.removeMessages([mockMessage.id]);
      });

      expect(removedMessages).toEqual([mockMessage2]);
      expect(result.current.messages).toEqual([mockMessage2]);
    });
  });

  describe("deleteSession", () => {
    it("should delete messages by session ID", () => {
      const { result } = renderHook(() => useMessagesStore());
      const session1Messages = [
        { ...mockMessage, session_id: "session-1" },
        { ...mockMachineMessage, session_id: "session-1" },
      ];
      const session2Messages = [{ ...mockMessage2, session_id: "session-2" }];

      act(() => {
        result.current.setMessages([...session1Messages, ...session2Messages]);
      });
      expect(result.current.messages).toHaveLength(3);

      act(() => {
        result.current.deleteSession("session-1");
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0].session_id).toBe("session-2");
    });

    it("should handle deleting non-existent session", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      act(() => {
        result.current.deleteSession("non-existent-session");
      });

      expect(result.current.messages).toHaveLength(1);
      expect(result.current.messages[0]).toEqual(mockMessage);
    });

    it("should handle deleting session from empty messages", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.deleteSession("any-session");
      });

      expect(result.current.messages).toEqual([]);
    });
  });

  describe("state isolation and concurrency", () => {
    it("should maintain state consistency across multiple operations", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
        result.current.addMessage(mockMessage2);
        result.current.updateMessageText(mockMessage.id, " - updated");
      });

      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0].text).toBe("Hello world - updated");
      expect(result.current.messages[1]).toEqual(mockMessage2);
    });

    it("should handle rapid message updates", () => {
      const { result } = renderHook(() => useMessagesStore());

      act(() => {
        result.current.setMessages([mockMessage]);
      });

      act(() => {
        for (let i = 0; i < 10; i++) {
          result.current.updateMessageText(mockMessage.id, ` ${i}`);
        }
      });

      expect(result.current.messages[0].text).toBe(
        "Hello world 0 1 2 3 4 5 6 7 8 9",
      );
    });
  });

  describe("edge cases", () => {
    it("should handle message with all optional fields", () => {
      const { result } = renderHook(() => useMessagesStore());
      const messageWithOptionals: Message = {
        ...mockMessage,
        category: "test-category",
        properties: { key: "value", nested: { prop: true } },
        content_blocks: [{ type: "text", content: "block content" } as any],
      };

      act(() => {
        result.current.addMessage(messageWithOptionals);
      });

      expect(result.current.messages[0]).toEqual(messageWithOptionals);
    });

    it("should handle message with empty arrays and strings", () => {
      const { result } = renderHook(() => useMessagesStore());
      const emptyMessage: Message = {
        ...mockMessage,
        text: "",
        files: [],
        sender_name: "",
      };

      act(() => {
        result.current.addMessage(emptyMessage);
      });

      expect(result.current.messages[0]).toEqual(emptyMessage);
    });

    it("should preserve message order during updates", () => {
      const { result } = renderHook(() => useMessagesStore());
      const messages = [mockMessage, mockMachineMessage, mockMessage2];

      act(() => {
        result.current.setMessages(messages);
      });

      act(() => {
        result.current.updateMessage({
          ...mockMachineMessage,
          text: "Updated middle message",
        });
      });

      expect(result.current.messages[0]).toEqual(mockMessage);
      expect(result.current.messages[1].text).toBe("Updated middle message");
      expect(result.current.messages[2]).toEqual(mockMessage2);
    });
  });
});
