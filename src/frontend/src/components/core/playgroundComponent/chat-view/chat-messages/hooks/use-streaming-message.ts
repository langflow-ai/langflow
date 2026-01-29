import { useEffect, useRef, useState } from "react";
import useAlertStore from "@/stores/alertStore";
import { ChatMessageType } from "@/types/chat";

interface UseStreamingMessageProps {
  chat: ChatMessageType;
  isBuilding: boolean;
  updateChat?: (chat: ChatMessageType, message: string) => void;
}

export function useStreamingMessage({
  chat,
  isBuilding,
  updateChat,
}: UseStreamingMessageProps) {
  const [streamUrl, setStreamUrl] = useState(chat.stream_url);
  // We need to check if message is not undefined because
  // we need to run .toString() on it
  const [chatMessage, setChatMessage] = useState(
    chat.message ? chat.message.toString() : "",
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSource = useRef<EventSource | undefined>(undefined);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const chatMessageRef = useRef(chatMessage);

  useEffect(() => {
    const chatMessageString = chat.message ? chat.message.toString() : "";
    setChatMessage(chatMessageString);
    chatMessageRef.current = chatMessageString;
  }, [chat, isBuilding]);

  // Keep ref in sync with state for streaming updates
  useEffect(() => {
    chatMessageRef.current = chatMessage;
  }, [chatMessage]);

  // The idea now is that chat.stream_url MAY be a URL if we should stream the output of the chat
  // probably the message is empty when we have a stream_url
  // what we need is to update the chat_message with the SSE data
  const streamChunks = (url: string) => {
    setIsStreaming(true); // Streaming starts
    return new Promise<boolean>((resolve, reject) => {
      eventSource.current = new EventSource(url);
      eventSource.current.onmessage = (event) => {
        const parsedData = JSON.parse(event.data);
        if (parsedData.chunk) {
          setChatMessage((prev) => {
            const newMessage = prev + parsedData.chunk;
            chatMessageRef.current = newMessage;
            return newMessage;
          });
        }
      };
      eventSource.current.onerror = (event: Event) => {
        setIsStreaming(false);
        eventSource.current?.close();
        setStreamUrl(undefined);
        const errorEvent = event as MessageEvent;
        if (errorEvent.data && JSON.parse(errorEvent.data)?.error) {
          setErrorData({
            title: "Error on Streaming",
            list: [JSON.parse(errorEvent.data)?.error],
          });
        }
        updateChat?.(chat, chatMessageRef.current);
        reject(new Error("Streaming failed"));
      };
      eventSource.current.addEventListener("close", (event) => {
        setStreamUrl(undefined); // Update state to reflect the stream is closed
        eventSource.current?.close();
        setIsStreaming(false);
        resolve(true);
      });
    });
  };

  useEffect(() => {
    if (streamUrl && !isStreaming) {
      streamChunks(streamUrl)
        .then(() => {
          if (updateChat) {
            updateChat(chat, chatMessageRef.current);
          }
        })
        .catch((error) => {
          console.error(error);
        });
    }
  }, [streamUrl, chatMessage]);

  useEffect(() => {
    return () => {
      eventSource.current?.close();
    };
  }, []);

  // Decode the message for display
  let decodedMessage = chatMessage ?? "";
  try {
    decodedMessage = decodeURIComponent(chatMessage);
  } catch (_e) {
    // ignore decode errors
  }

  return {
    chatMessage: decodedMessage,
    isStreaming,
  };
}
