import { useState, useMemo } from "react";
import { v4 as uuid } from "uuid";
import { Button } from "@/components/ui/button";
import LoadingIcon from "@/components/ui/loading";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Square, Upload, X, File, Eye } from "lucide-react";
import SvgAutonomize from "@/icons/Autonomize/Autonomize";
import { FileUploadManager } from "./FileUploadManager";
import { FilePreviewModal } from "./FilePreviewModal";
import {
  PlaygroundTabProps,
  Message,
  FileInputComponent,
} from "./Playground.types";
import { DragIcon } from "@/assets/icons/DragIcon";
import { MARKETPLACE_TAGS } from "@/constants/marketplace-tags";
import { MessageRenderer } from "./MessageRender";
import { usePlaygroundChat } from "./PlaygroundChat";
import { useResizablePanel } from "./UseResizablePanel";

export default function PlaygroundTab({
  publishedFlowData,
}: PlaygroundTabProps) {
  const [input, setInput] = useState("");
  const [fileUrls, setFileUrls] = useState<Record<string, string>>({});
  const [isFileModalOpen, setIsFileModalOpen] = useState(false);
  const [previewFile, setPreviewFile] = useState<{
    url: string;
    name: string;
    type: string;
  } | null>(null);

  const { leftPanelWidth, isDragging, handleDragStart } = useResizablePanel(33.33);

  const {
    messages,
    isLoading,
    error,
    streamingMessageId,
    loadingDots,
    displayedTexts,
    targetTexts,
    sendMessage: sendMessageHook,
    stopStreaming,
    setError,
  } = usePlaygroundChat(publishedFlowData);

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
    const tag = MARKETPLACE_TAGS.find((t) => t.id === tagId);
    return tag ? tag.title : tagId;
  };

  const hasChatInput = useMemo(() => {
    if (!publishedFlowData?.flow_data?.nodes) return true;
    
    return publishedFlowData.flow_data.nodes.some((node: any) => {
      const nodeType = node.data?.type;
      return nodeType === "ChatInput" || nodeType === "TextInput";
    });
  }, [publishedFlowData]);

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

        const filename = getFilenameFromUrl(url);
        const extension = filename.split('.').pop()?.toLowerCase() || '';
        let fileType = 'application/octet-stream';
        
        if (extension === 'json') fileType = 'application/json';
        else if (extension === 'png') fileType = 'image/png';
        else if (extension === 'pdf') fileType = 'application/pdf';

        return {
          componentId,
          componentName: component.display_name,
          filename,
          url,
          fileType,
        };
      })
      .filter((file): file is NonNullable<typeof file> => file !== null);
  }, [fileUrls, fileInputComponents]);

  const sendMessage = async () => {
    if (hasChatInput && !input.trim()) return;
    if (!hasChatInput && selectedFiles.length === 0) return;
    if (isLoading) return;

    const currentFileUrls = { ...fileUrls };
    const messageText = hasChatInput ? input.trim() : "Processing uploaded file...";

    setFileUrls({});
    setInput("");
    
    await sendMessageHook(messageText, currentFileUrls, fileInputComponents);
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

  const handlePreviewFile = (file: typeof selectedFiles[0]) => {
    setPreviewFile({
      url: file.url,
      name: file.filename,
      type: file.fileType,
    });
  };

  return (
    <div className="flex h-full w-full flex-col ">
      <div className="flex flex-1 overflow-hidden h-full items-center">
        {/* Agent Details Panel */}
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

        {/* Drag Handle */}
        <div
          className="w-3 h-[28px] bg-[#F5F2FF] cursor-col-resize rounded-[4px] text-[#350E84] flex items-center justify-center"
          onMouseDown={handleDragStart}
        >
          <DragIcon />
        </div>

        {/* Chat Panel */}
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
                  {hasChatInput ? (
                    <>
                      <p className="text-sm mt-2">
                        Send a message to see how your agent responds
                      </p>
                      {fileInputComponents.length > 0 && (
                        <p className="text-xs mt-2 text-muted-foreground">
                          This agent accepts file inputs. Use the attachment button
                          to provide files.
                        </p>
                      )}
                    </>
                  ) : (
                    <>
                      <p className="text-sm mt-2">
                        Upload a file to process with this agent
                      </p>
                      <p className="text-xs mt-2 text-muted-foreground">
                        This agent processes files without requiring text input
                      </p>
                    </>
                  )}
                </div>
              </div>
            )}

            <div className="space-y-4 max-w-full">
              {messages.map((message) => (
                <MessageRenderer
                  key={message.id}
                  message={message}
                  displayedTexts={displayedTexts}
                  targetTexts={targetTexts}
                  loadingDots={loadingDots}
                />
              ))}
            </div>
          </div>

          {/* Input Area */}
          <div className="bg-background p-4 pt-0">
            {error && (
              <div className="mb-2 text-sm text-destructive">{error}</div>
            )}

            {selectedFiles.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-2">
                {selectedFiles.map((file) => (
                  <div
                    key={file.componentId}
                    className="flex items-center gap-2 bg-muted/50 border rounded-lg px-3 py-2 text-sm group hover:border-primary/50 transition-colors"
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
                    <div className="flex items-center gap-1 ml-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handlePreviewFile(file)}
                        className="h-6 w-6 p-0 text-muted-foreground hover:text-primary flex-shrink-0"
                        title="Preview file"
                      >
                        <Eye className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeSelectedFile(file.componentId)}
                        className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive flex-shrink-0"
                        title="Remove file"
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="max-w-full">
              {hasChatInput ? (
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
                        <Upload className="h-4 w-4" />
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
              ) : (
                <div className="flex items-center justify-center gap-3">
                  <Button
                    onClick={() => setIsFileModalOpen(true)}
                    disabled={isLoading || !!streamingMessageId}
                    variant="outline"
                    size="lg"
                    className="flex-1 max-w-md gap-2"
                  >
                    <Upload className="h-5 w-5" />
                    {selectedFiles.length > 0 ? "Change File" : "Upload File"}
                  </Button>

                  {selectedFiles.length > 0 && (
                    <button
                      onClick={streamingMessageId ? stopStreaming : sendMessage}
                      disabled={!streamingMessageId && isLoading}
                      className={`px-6 py-2.5 rounded-md transition-colors ${
                        streamingMessageId
                          ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                          : "bg-primary text-primary-foreground hover:bg-primary/90"
                      } disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2`}
                      aria-label={
                        streamingMessageId ? "Stop generation" : "Process file"
                      }
                    >
                      {streamingMessageId ? (
                        <>
                          <Square className="h-4 w-4" />
                          Stop
                        </>
                      ) : isLoading ? (
                        <>
                          <LoadingIcon />
                          Processing
                        </>
                      ) : (
                        <>
                          <ForwardedIconComponent name="Play" className="h-4 w-4" />
                          Process
                        </>
                      )}
                    </button>
                  )}
                </div>
              )}
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

      {previewFile && (
        <FilePreviewModal
          isOpen={!!previewFile}
          onClose={() => setPreviewFile(null)}
          fileUrl={previewFile.url}
          fileName={previewFile.name}
          fileType={previewFile.type}
        />
      )}
    </div>
  );
}