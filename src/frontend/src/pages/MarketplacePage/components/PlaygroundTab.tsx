import { useState, useRef, useEffect } from "react";
import { v4 as uuid } from "uuid";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import LoadingIcon from "@/components/ui/loading";
import { getURL } from "@/controllers/API/helpers/constants";
import { Square } from "lucide-react";
import { hasMarkdownFormatting } from "@/utils/markdownUtils";

interface PlaygroundTabProps {
  publishedFlowData: any;
}

interface Message {
  id: string;
  type: "user" | "agent";
  text: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export default function PlaygroundTab({ publishedFlowData }: PlaygroundTabProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(() => uuid());
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [loadingDots, setLoadingDots] = useState(1);

  // Typing animation state - stores target text (from backend) and displayed text (animated)
  const [targetTexts, setTargetTexts] = useState<Map<string, string>>(new Map());
  const [displayedTexts, setDisplayedTexts] = useState<Map<string, string>>(new Map());

  // Ref to access latest targetTexts without restarting animation
  const targetTextsRef = useRef<Map<string, string>>(new Map());

  const abortControllerRef = useRef<AbortController | null>(null);

  // Sync targetTexts to ref without restarting animation
  useEffect(() => {
    targetTextsRef.current = targetTexts;
  }, [targetTexts]);

  // Animate "Working." dots when streaming with empty text
  useEffect(() => {
    // Check if we have a streaming message with no text
    const hasEmptyStreamingMessage = messages.some(
      msg => msg.isStreaming && !msg.text
    );

    if (hasEmptyStreamingMessage) {
      const interval = setInterval(() => {
        setLoadingDots(prev => (prev % 3) + 1);
      }, 500);

      return () => clearInterval(interval);
    } else {
      setLoadingDots(1); // Reset when done
    }
  }, [messages]);

  // Character-by-character typing animation effect (runs continuously, never restarts)
  useEffect(() => {
    const interval = setInterval(() => {
      setDisplayedTexts(prev => {
        const next = new Map(prev);
        let hasChanges = false;

        // Use ref to access latest targets without restarting interval
        targetTextsRef.current.forEach((target, messageId) => {
          const current = prev.get(messageId) || "";

          // If we haven't shown all the text yet, reveal more characters
          if (current.length < target.length) {
            // Reveal multiple characters at once for faster typing (5 chars per tick)
            const charsToAdd = Math.min(5, target.length - current.length);
            next.set(messageId, target.substring(0, current.length + charsToAdd));
            hasChanges = true;
          }
        });

        return hasChanges ? next : prev;
      });
    }, 20); // 20ms = ~250 characters per second for smooth, fast typing

    return () => clearInterval(interval);
  }, []); // Empty deps - runs once, never restarts

  const handleStreamEvent = (eventData: any, localAgentMessageId: string) => {
    // Handle event wrapper format: {"event": "...", "data": {...}}
    const data = eventData?.data;

    if (!data) return;

    // Handle add_message events
    if (eventData.event === "add_message") {
      // Ignore User sender events (they just echo our input)
      if (data.sender === "User") {
        return;
      }

      // Handle Machine/Agent sender events
      if (data.sender === "Machine") {
        const backendId = data.id;
        const text = data.text || "";
        const state = data.properties?.state || "partial";
        const isComplete = state === "complete";

        // Store target text for typing animation
        setTargetTexts(prev => {
          const next = new Map(prev);
          next.set(backendId, text);
          return next;
        });

        // Initialize displayedTexts on first chunk to prevent flicker
        setDisplayedTexts(prev => {
          if (!prev.has(backendId)) {
            const next = new Map(prev);
            // Transfer from local ID to preserve "Working..." animation
            const currentDisplayed = prev.get(localAgentMessageId) || "";
            next.set(backendId, currentDisplayed);
            // Clean up old local ID entry to avoid memory leak
            next.delete(localAgentMessageId);
            return next;
          }
          return prev;
        });

        // Update or create Agent message using backend ID
        setMessages((prev) => {
          // Check if we already have this message (by backend ID)
          const existingIndex = prev.findIndex(msg => msg.id === backendId);

          if (existingIndex !== -1) {
            // Update streaming state - only set text when complete to avoid flicker
            return prev.map(msg =>
              msg.id === backendId
                ? { ...msg, text: isComplete ? text : "", isStreaming: !isComplete }
                : msg
            );
          } else {
            // First time seeing this backend ID
            // Check if we have a local placeholder to replace
            const placeholderIndex = prev.findIndex(msg => msg.id === localAgentMessageId);

            if (placeholderIndex !== -1) {
              // Replace the local placeholder with backend ID
              return prev.map(msg =>
                msg.id === localAgentMessageId
                  ? { ...msg, id: backendId, text: isComplete ? text : "", isStreaming: !isComplete }
                  : msg
              );
            } else {
              // No placeholder found, create new message
              return [...prev, {
                id: backendId,
                type: "agent" as const,
                text: isComplete ? text : "",
                timestamp: new Date(),
                isStreaming: !isComplete
              }];
            }
          }
        });

        // When streaming completes, clean up the Maps after animation finishes
        if (isComplete) {
          setTimeout(() => {
            setTargetTexts(prev => {
              const next = new Map(prev);
              next.delete(backendId);
              return next;
            });
            setDisplayedTexts(prev => {
              const next = new Map(prev);
              next.delete(backendId);
              return next;
            });
          }, 2000); // Wait 2 seconds for animation to complete
        }
      }
    } else if (eventData.event === "end") {
      // Stream completed - mark all messages as complete
      setMessages((prev) =>
        prev.map(msg => ({ ...msg, isStreaming: false }))
      );
    } else if (eventData.event === "error") {
      // Handle error event
      const errorMsg = data?.error || "Stream error";
      throw new Error(errorMsg);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userInputText = input.trim();

    // Create user message
    const userMessage: Message = {
      id: uuid(),
      type: "user",
      text: userInputText,
      timestamp: new Date(),
    };

    // Create empty agent message placeholder for streaming
    const localAgentMessageId = uuid();
    const agentMessage: Message = {
      id: localAgentMessageId,
      type: "agent",
      text: "",
      timestamp: new Date(),
      isStreaming: true,
    };

    // Initialize displayedTexts with local ID to show "Working..." immediately
    setDisplayedTexts(prev => {
      const next = new Map(prev);
      next.set(localAgentMessageId, ""); // Initialize with empty string
      return next;
    });

    setMessages((prev) => [...prev, userMessage, agentMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);
    setStreamingMessageId(localAgentMessageId);

    // Create abort controller for stop functionality
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      // Use fetch for streaming support
      const response = await fetch(
        `${getURL("RUN")}/${publishedFlowData.flow_id}?stream=true`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            input_value: userInputText,
            session_id: sessionId,
          }),
          signal: abortController.signal,
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Get streaming reader
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response body");
      }

      let buffer = "";

      // Read stream chunks
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        // Decode chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Split by double newline (SSE format) or single newline
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || ""; // Keep incomplete chunk

        // Process each complete chunk
        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            // Parse the JSON event
            const eventData = JSON.parse(line);

            // Handle the event using our new handler
            handleStreamEvent(eventData, localAgentMessageId);
          } catch (e) {
            console.error("[Playground] Error parsing chunk:", e, line);
          }
        }
      }

      // Process any remaining buffer
      if (buffer.trim()) {
        try {
          const eventData = JSON.parse(buffer);
          handleStreamEvent(eventData, localAgentMessageId);
        } catch (e) {
          // Ignore parse errors for final buffer
        }
      }

      // Mark streaming complete
      setMessages((prev) =>
        prev.map((msg) => ({ ...msg, isStreaming: false }))
      );
    } catch (err: any) {
      console.error("Streaming error:", err);

      if (err.name === "AbortError") {
        // User clicked Stop button
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === localAgentMessageId
              ? { ...msg, text: msg.text + " [stopped]", isStreaming: false }
              : msg
          )
        );
      } else {
        const errorMessage = err.message || "Streaming failed";
        setError(errorMessage);

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === localAgentMessageId
              ? { ...msg, text: `Error: ${errorMessage}`, isStreaming: false }
              : msg
          )
        );
      }
    } finally {
      setIsLoading(false);
      setStreamingMessageId(null);
      abortControllerRef.current = null;
    }
  };

  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-full w-full flex-col bg-background">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <div className="text-center">
              <p className="text-lg font-medium">Start a conversation</p>
              <p className="text-sm mt-2">Send a message to test this flow</p>
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.type === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.type === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-foreground"
              }`}
            >
              <div className="break-words">
                {(() => {
                  // For agent messages, use typing animation if available
                  if (message.type === "agent") {
                    const displayedText = displayedTexts.get(message.id);
                    const textToRender = displayedText !== undefined
                      ? (displayedText || `Working${'.'.repeat(loadingDots)}`)
                      : (message.text || "");

                    // Smart detection: Only render as Markdown if patterns detected
                    if (hasMarkdownFormatting(textToRender)) {
                      return (
                        <Markdown
                          remarkPlugins={[remarkGfm]}
                          className="prose prose-sm dark:prose-invert max-w-none"
                        >
                          {textToRender}
                        </Markdown>
                      );
                    } else {
                      // Plain text response - keep as-is with whitespace preservation
                      return <div className="whitespace-pre-wrap">{textToRender}</div>;
                    }
                  }

                  // For user messages, always plain text
                  return <div className="whitespace-pre-wrap">{message.text}</div>;
                })()}
                {message.isStreaming && message.type === "agent" && (() => {
                  const displayedText = displayedTexts.get(message.id) || "";
                  const targetText = targetTexts.get(message.id) || message.text;
                  // Show cursor if we have text and still typing
                  return displayedText && displayedText.length > 0 && displayedText.length <= targetText.length;
                })() && (
                  <span className="inline-block w-0.5 h-5 ml-0.5 bg-foreground animate-pulse"></span>
                )}
              </div>
              {/* Timestamp - hide for agent messages during "Working..." state */}
              {(() => {
                // For user messages, always show timestamp
                if (message.type === "user") {
                  return (
                    <div className="text-xs opacity-70 mt-1">
                      {message.timestamp.toLocaleTimeString()}
                    </div>
                  );
                }

                // For agent messages, only show timestamp if we have actual text
                if (message.type === "agent") {
                  const displayedText = displayedTexts.get(message.id);

                  // If message is in typing animation and has text, show timestamp
                  if (displayedText !== undefined && displayedText.length > 0) {
                    return (
                      <div className="text-xs opacity-70 mt-1">
                        {message.timestamp.toLocaleTimeString()}
                      </div>
                    );
                  }

                  // If message is completed (not in Map) and has text, show timestamp
                  if (displayedText === undefined && message.text) {
                    return (
                      <div className="text-xs opacity-70 mt-1">
                        {message.timestamp.toLocaleTimeString()}
                      </div>
                    );
                  }

                  // Hide during "Working..." state (no text yet)
                  return null;
                }

                return null;
              })()}
            </div>
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div className="border-t border-border p-4">
        {error && (
          <div className="mb-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
            className="flex-1 min-h-[60px] max-h-[120px] resize-none"
            disabled={isLoading || !!streamingMessageId}
          />
          <Button
            onClick={streamingMessageId ? stopStreaming : sendMessage}
            disabled={!streamingMessageId && (!input.trim() || isLoading)}
            className="self-end"
            variant={streamingMessageId ? "destructive" : "default"}
          >
            {streamingMessageId ? (
              <>
                <Square className="h-4 w-4 mr-2" />
                Stop
              </>
            ) : isLoading ? (
              <LoadingIcon />
            ) : (
              "Send"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
