import { useState, useRef, useEffect, useMemo } from "react";
import { v4 as uuid } from "uuid";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import LoadingIcon from "@/components/ui/loading";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { getURL } from "@/controllers/API/helpers/constants";
import { Square, Paperclip, X, File } from "lucide-react";
import { hasMarkdownFormatting } from "@/utils/markdownUtils";
import SvgAutonomize from "@/icons/Autonomize/Autonomize";
import { FileUploadManager } from "./FileUploadManager";
import {
  PlaygroundTabProps,
  Message,
  FileInputComponent,
} from "./Playground.types";
import { DragIcon } from "@/assets/icons/DragIcon";
import { MARKETPLACE_TAGS } from "@/constants/marketplace-tags";

export default function PlaygroundTab({
  publishedFlowData,
}: PlaygroundTabProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(() => uuid());
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(
    null
  );
  const [loadingDots, setLoadingDots] = useState(1);
  const [fileUrls, setFileUrls] = useState<Record<string, string>>({});
  const [isFileModalOpen, setIsFileModalOpen] = useState(false);
  const [leftPanelWidth, setLeftPanelWidth] = useState(33.33);
  const [isDragging, setIsDragging] = useState(false);

  const agentDetails = {
    createdOn: publishedFlowData?.created_at
      ? new Date(publishedFlowData.created_at).toLocaleString()
      : "N/A",
    lastUpdatedOn: publishedFlowData?.updated_at
      ? new Date(publishedFlowData.updated_at).toLocaleString()
      : "N/A",
    description: publishedFlowData?.description || "No description available",
    version: publishedFlowData?.version || "1.0",
    tags: publishedFlowData?.tags || [],
    name: publishedFlowData?.name || "Agent",
  };

   const getTagTitle = (tagId: string): string => {
    const tag = MARKETPLACE_TAGS.find(t => t.id === tagId);
    return tag ? tag.title : tagId;
  };

  const fileInputComponents: FileInputComponent[] = useMemo(() => {
    const components: FileInputComponent[] = [];

    if (!publishedFlowData?.flow_data?.nodes) {
      return components;
    }

    publishedFlowData.flow_data.nodes.forEach((node: any) => {
      const nodeData = node.data?.node;
      if (!nodeData?.template) return;

      if (node.data.type === "FilePathInput") {
        components.push({
          id: node.id,
          type: node.data.type,
          display_name: nodeData.display_name || node.data.type,
          inputKey: "input_value",
        });
      }
    });

    return components;
  }, [publishedFlowData]);

  const selectedFiles = useMemo(() => {
    return Object.entries(fileUrls)
      .map(([componentId, url]) => {
        const component = fileInputComponents.find((c) => c.id === componentId);
        if (!component || !url) return null;

        const getFilenameFromUrl = (url: string) => {
          try {
            const urlObj = new URL(url);
            const pathname = urlObj.pathname;
            const parts = pathname.split("/");
            const filename = parts[parts.length - 1];

            const match = filename.match(/^[0-9a-f-]+_(.+)$/i);
            return match ? match[1] : filename || "Unknown file";
          } catch {
            return "Unknown file";
          }
        };

        return {
          componentId,
          componentName: component.display_name,
          filename: getFilenameFromUrl(url),
          url,
        };
      })
      .filter((file): file is NonNullable<typeof file> => file !== null);
  }, [fileUrls, fileInputComponents]);

  const handleDragStart = () => {
    setIsDragging(true);
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;

      const containerWidth = window.innerWidth;
      const newLeftWidth = (e.clientX / containerWidth) * 100;

      if (newLeftWidth >= 20 && newLeftWidth <= 60) {
        setLeftPanelWidth(newLeftWidth);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.body.style.userSelect = "none";
      document.body.style.cursor = "col-resize";
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    } else {
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };
  }, [isDragging]);

  const createFileInputTweaks = (fileUrls: Record<string, string>) => {
    const tweaks: Record<string, any> = {};

    fileInputComponents.forEach((component) => {
      const fileUrl = fileUrls[component.id];
      if (fileUrl) {
        tweaks[component.id] = {
          input_value: fileUrl,
        };
      }
    });

    return tweaks;
  };

  const [targetTexts, setTargetTexts] = useState<Map<string, string>>(
    new Map()
  );
  const [displayedTexts, setDisplayedTexts] = useState<Map<string, string>>(
    new Map()
  );
  const targetTextsRef = useRef<Map<string, string>>(new Map());
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    targetTextsRef.current = targetTexts;
  }, [targetTexts]);

  useEffect(() => {
    const hasEmptyStreamingMessage = messages.some(
      (msg) => msg.isStreaming && !msg.text
    );

    if (hasEmptyStreamingMessage) {
      const interval = setInterval(() => {
        setLoadingDots((prev) => (prev % 3) + 1);
      }, 500);

      return () => clearInterval(interval);
    } else {
      setLoadingDots(1);
    }
  }, [messages]);

  useEffect(() => {
    const interval = setInterval(() => {
      setDisplayedTexts((prev) => {
        const next = new Map(prev);
        let hasChanges = false;

        targetTextsRef.current.forEach((target, messageId) => {
          const current = prev.get(messageId) || "";

          if (current.length < target.length) {
            const charsToAdd = Math.min(5, target.length - current.length);
            next.set(
              messageId,
              target.substring(0, current.length + charsToAdd)
            );
            hasChanges = true;
          }
        });

        return hasChanges ? next : prev;
      });
    }, 20);

    return () => clearInterval(interval);
  }, []);

  const handleStreamEvent = (eventData: any, localAgentMessageId: string) => {
    const data = eventData?.data;
    if (!data) return;

    if (eventData.event === "add_message") {
      if (data.sender === "User") return;

      if (data.sender === "Machine") {
        const backendId = data.id;
        const text = data.text || "";
        const state = data.properties?.state || "partial";
        const isComplete = state === "complete";

        setTargetTexts((prev) => {
          const next = new Map(prev);
          next.set(backendId, text);
          return next;
        });

        setDisplayedTexts((prev) => {
          if (!prev.has(backendId)) {
            const next = new Map(prev);
            const currentDisplayed = prev.get(localAgentMessageId) || "";
            next.set(backendId, currentDisplayed);
            next.delete(localAgentMessageId);
            return next;
          }
          return prev;
        });

        setMessages((prev) => {
          const existingIndex = prev.findIndex((msg) => msg.id === backendId);

          if (existingIndex !== -1) {
            return prev.map((msg) =>
              msg.id === backendId
                ? {
                    ...msg,
                    text: isComplete ? text : "",
                    isStreaming: !isComplete,
                  }
                : msg
            );
          } else {
            const placeholderIndex = prev.findIndex(
              (msg) => msg.id === localAgentMessageId
            );

            if (placeholderIndex !== -1) {
              return prev.map((msg) =>
                msg.id === localAgentMessageId
                  ? {
                      ...msg,
                      id: backendId,
                      text: isComplete ? text : "",
                      isStreaming: !isComplete,
                    }
                  : msg
              );
            } else {
              return [
                ...prev,
                {
                  id: backendId,
                  type: "agent" as const,
                  text: isComplete ? text : "",
                  timestamp: new Date(),
                  isStreaming: !isComplete,
                },
              ];
            }
          }
        });

        if (isComplete) {
          setTimeout(() => {
            setTargetTexts((prev) => {
              const next = new Map(prev);
              next.delete(backendId);
              return next;
            });
            setDisplayedTexts((prev) => {
              const next = new Map(prev);
              next.delete(backendId);
              return next;
            });
          }, 2000);
        }
      }
    } else if (eventData.event === "end") {
      setMessages((prev) =>
        prev.map((msg) => ({ ...msg, isStreaming: false }))
      );
    } else if (eventData.event === "error") {
      const errorMsg = data?.error || "Stream error";
      throw new Error(errorMsg);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userInputText = input.trim();
    const userMessage: Message = {
      id: uuid(),
      type: "user",
      text: userInputText,
      timestamp: new Date(),
    };

    const localAgentMessageId = uuid();
    const agentMessage: Message = {
      id: localAgentMessageId,
      type: "agent",
      text: "",
      timestamp: new Date(),
      isStreaming: true,
    };

    setDisplayedTexts((prev) => {
      const next = new Map(prev);
      next.set(localAgentMessageId, "");
      return next;
    });

    setMessages((prev) => [...prev, userMessage, agentMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);
    setStreamingMessageId(localAgentMessageId);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const fileTweaks = createFileInputTweaks(fileUrls);

      const requestBody = {
        output_type: "chat",
        input_type: "chat",
        input_value: userInputText,
        session_id: sessionId,
        ...(Object.keys(fileTweaks).length > 0 && { tweaks: fileTweaks }),
      };

      const response = await fetch(
        `${getURL("RUN")}/${publishedFlowData.flow_id}?stream=true`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(requestBody),
          signal: abortController.signal,
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response body");
      }

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const eventData = JSON.parse(line);
            handleStreamEvent(eventData, localAgentMessageId);
          } catch (e) {
            console.error("[Playground] Error parsing chunk:", e, line);
          }
        }
      }

      if (buffer.trim()) {
        try {
          const eventData = JSON.parse(buffer);
          handleStreamEvent(eventData, localAgentMessageId);
        } catch (e) {
        }
      }

      setMessages((prev) =>
        prev.map((msg) => ({ ...msg, isStreaming: false }))
      );
    } catch (err: any) {
      console.error("Streaming error:", err);

      if (err.name === "AbortError") {
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

  const handleFileUrlChange = (componentId: string, url: string) => {
    setFileUrls((prev) => ({
      ...prev,
      [componentId]: url,
    }));
  };

  const clearFileUrl = (componentId: string) => {
    setFileUrls((prev) => {
      const newUrls = { ...prev };
      delete newUrls[componentId];
      return newUrls;
    });
  };

  const removeSelectedFile = (componentId: string) => {
    clearFileUrl(componentId);
  };

  return (
    <div className="flex h-full w-full flex-col ">
      <div className="flex flex-1 overflow-hidden h-full items-center">
        <div
          className="flex flex-col rounded-lg border border-border dark:border-white/20 h-full"
          style={{ width: `${leftPanelWidth}%` }}
        >
          <div className="bg-white rounded-lg p-4 flex-1 overflow-y-auto">
            <h3 className="text-sm font-medium mb-4 text-[#444]">
              Agent Details
            </h3>
            <div className="text-sm space-y-4">
              <p className="">
                <span className="text-[#64616A] text-xs">
                  Created On: {agentDetails.createdOn} {"  "}
                </span>
                {"  "}
                <span className="text-[#64616A] text-xs">
                  Last Updated On: {agentDetails.lastUpdatedOn}
                </span>
              </p>

              <div className="space-y-2">
                <p className="text-[#444] text-xs font-medium">Description:</p>
                <p className="text-[#64616A] text-xs">
                  {agentDetails.description}
                </p>
                <p className="text-[#64616A] text-xs font-medium">
                  Version: {agentDetails.version}
                </p>
              </div>
              <div className="space-y-2">
                <p className="text-[#444] text-xs font-medium">Domain:</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {agentDetails.tags.map((tag: string, index: number) => (
                    <span
                      key={index}
                      className="bg-[#F5F2FF] text-[#64616A] text-xs px-2 py-1 rounded-[4px]"
                    >
                      {getTagTitle(tag)}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div
          className="w-3 h-[28px] bg-[#F5F2FF] cursor-col-resize rounded-[4px] text-[#350E84] flex items-center justify-center"
          onMouseDown={handleDragStart}
        >
          <DragIcon />
        </div>

        <div
          className="flex flex-col bg-background overflow-hidden rounded-lg border border-border dark:border-white/20 h-full"
          style={{
            width: `${100 - leftPanelWidth}%`,
            pointerEvents: isDragging ? "none" : "auto",
          }}
        >
          <div className="bg-white rounded-lg p-3 flex-1 overflow-y-auto scrollbar-hide">
            {messages.length === 0 && (
              <div className="flex h-full items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <div className="mb-4">
                    <SvgAutonomize
                      title="Autonomize logo"
                      className="h-10 w-10 scale-[1.5] mx-auto opacity-60"
                    />
                  </div>
                  <p className="text-sm mt-2">
                    Send a message to see how your agent responds
                  </p>
                  {fileInputComponents.length > 0 && (
                    <p className="text-xs mt-2 text-muted-foreground">
                      This agent accepts file inputs. Use the attachment button
                      to provide files.
                    </p>
                  )}
                </div>
              </div>
            )}

            <div className="space-y-4 max-w-full">
              {messages.map((message) => (
                <div key={message.id} className="space-y-2">
                  <div
                    className={`flex ${
                      message.type === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg px-4 py-3 ${
                        message.type === "user"
                          ? "bg-[#350E84] text-white"
                          : "bg-[#F8F9FA] text-[#444] border"
                      }`}
                    >
                      <div className="break-words">
                        {(() => {
                          if (message.type === "agent") {
                            const displayedText = displayedTexts.get(
                              message.id
                            );
                            const textToRender =
                              displayedText !== undefined
                                ? displayedText ||
                                  `Working${".".repeat(loadingDots)}`
                                : message.text || "";

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
                              return (
                                <div className="whitespace-pre-wrap">
                                  {textToRender}
                                </div>
                              );
                            }
                          }
                          return (
                            <div className="whitespace-pre-wrap">
                              {message.text}
                            </div>
                          );
                        })()}
                        {message.isStreaming &&
                          message.type === "agent" &&
                          (() => {
                            const displayedText =
                              displayedTexts.get(message.id) || "";
                            const targetText =
                              targetTexts.get(message.id) || message.text;
                            return (
                              displayedText &&
                              displayedText.length > 0 &&
                              displayedText.length <= targetText.length
                            );
                          })() && (
                            <span className="inline-block w-0.5 h-5 ml-0.5 bg-foreground animate-pulse"></span>
                          )}
                      </div>
                    </div>
                  </div>

                  <div
                    className={`flex text-xs text-muted-foreground ${
                      message.type === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    {(() => {
                      if (message.type === "user") {
                        return (
                          <span className="px-4">
                            {message.timestamp.toLocaleTimeString()}
                          </span>
                        );
                      }

                      if (message.type === "agent") {
                        const displayedText = displayedTexts.get(message.id);

                        if (
                          displayedText !== undefined &&
                          displayedText.length > 0
                        ) {
                          return (
                            <span className="px-4">
                              {message.timestamp.toLocaleTimeString()}
                            </span>
                          );
                        }

                        if (displayedText === undefined && message.text) {
                          return (
                            <span className="px-4">
                              {message.timestamp.toLocaleTimeString()}
                            </span>
                          );
                        }

                        return null;
                      }

                      return null;
                    })()}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-background p-4 pt-0">
            {error && (
              <div className="mb-2 text-sm text-destructive">{error}</div>
            )}

            {selectedFiles.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-2">
                {selectedFiles.map((file) => (
                  <div
                    key={file.componentId}
                    className="flex items-center gap-2 bg-muted/50 border rounded-lg px-3 py-2 text-sm"
                  >
                    <File className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <div className="flex flex-col min-w-0">
                      <span
                        className="font-medium truncate max-w-[200px]"
                        title={file.filename}
                      >
                        {file.filename}
                      </span>
                      <span
                        className="text-xs text-muted-foreground truncate"
                        title={file.componentName}
                      >
                        for {file.componentName}
                      </span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeSelectedFile(file.componentId)}
                      className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive ml-1 flex-shrink-0"
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            )}

            <div className="max-w-full">
              <div className="relative">
                <textarea
                  value={input}
                  rows={1}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Type your message..."
                  className="w-full p-3 pr-20 rounded-lg border border-input bg-background text-sm resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                  onKeyDown={handleKeyPress}
                  disabled={isLoading || !!streamingMessageId}
                />

                <div className="absolute right-2 top-1.5 flex items-center gap-1">
                  {fileInputComponents.length > 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={isLoading || !!streamingMessageId}
                      className="h-8 w-8 p-0 hover:bg-muted"
                      onClick={() => setIsFileModalOpen(true)}
                    >
                      <Paperclip className="h-4 w-4" />
                    </Button>
                  )}

                  <button
                    onClick={streamingMessageId ? stopStreaming : sendMessage}
                    disabled={
                      !streamingMessageId && (!input.trim() || isLoading)
                    }
                    className={`p-2 rounded-md transition-colors ${
                      streamingMessageId
                        ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        : "bg-primary text-primary-foreground hover:bg-primary/90"
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                    aria-label={
                      streamingMessageId ? "Stop generation" : "Submit message"
                    }
                  >
                    {streamingMessageId ? (
                      <Square className="h-4 w-4" />
                    ) : isLoading ? (
                      <LoadingIcon />
                    ) : (
                      <ForwardedIconComponent name="Send" className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <FileUploadManager
        isOpen={isFileModalOpen}
        onClose={() => setIsFileModalOpen(false)}
        fileInputComponents={fileInputComponents}
        fileUrls={fileUrls}
        onFileUrlChange={handleFileUrlChange}
        onClearFileUrl={clearFileUrl}
        onError={setError}
      />
    </div>
  );
}