import React, { RefObject } from "react";
import { Button } from "@/components/ui/button";
import LoadingIcon from "@/components/ui/loading";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Square, Upload, X, File, Eye } from "lucide-react";
import SvgAutonomize from "@/icons/Autonomize/Autonomize";
import { MessageRenderer } from "./MessageRender";
import { Message, FileInputComponent } from "./Playground.types";

interface SelectedFileItem {
  componentId: string;
  componentName: string;
  filename: string;
  url: string;
  fileType: string;
}

interface ChatAreaProps {
  // Chat messages
  messages: Message[];
  displayedTexts: Map<string, string>;
  targetTexts: Map<string, string>;
  loadingDots: number;
  onPreviewAttachment: (f: { url: string; name: string; type: string }) => void;
  onPreviewSampleFile: (filePathOrName: string) => void;

  // Thread info
  threadId?: string;
  onNewThread?: () => void;
  onOpenThreadLogs?: () => void;
  disableThreadLogs?: boolean;

  // Scrolling
  chatContainerRef: RefObject<HTMLDivElement>;
  onScroll: () => void;

  // Error
  error: string | null;

  // Files
  selectedFiles: SelectedFileItem[];
  onPreviewFile: (file: SelectedFileItem) => void;
  onRemoveSelectedFile: (componentId: string) => void;

  // Input/config
  hasChatInput: boolean;
  input: string;
  setInput: (v: string) => void;
  streamingMessageId: string | null;
  isLoading: boolean;
  onSend: () => void;
  onStop: () => void;

  fileInputComponents: FileInputComponent[];
  onOpenFileModal: () => void;
  textareaRef: RefObject<HTMLTextAreaElement>;
  autoResizeTextarea: () => void;
  onKeyPress: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;

  // Samples
  showSampleSection: boolean;
  sampleFileNames: string[];
  sampleFilePaths: string[];
  onSelectSampleFile: (filePathOrName: string) => void;
}

export function ChatArea({
  messages,
  displayedTexts,
  targetTexts,
  loadingDots,
  onPreviewAttachment,
  onPreviewSampleFile,
  threadId,
  onNewThread,
  onOpenThreadLogs,
  disableThreadLogs,
  chatContainerRef,
  onScroll,
  error,
  selectedFiles,
  onPreviewFile,
  onRemoveSelectedFile,
  hasChatInput,
  input,
  setInput,
  streamingMessageId,
  isLoading,
  onSend,
  onStop,
  fileInputComponents,
  onOpenFileModal,
  textareaRef,
  autoResizeTextarea,
  onKeyPress,
  showSampleSection,
  sampleFileNames,
  sampleFilePaths,
  onSelectSampleFile,
}: ChatAreaProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Thread Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-white border-b">
        <div className="text-xs text-[#444] font-medium truncate max-w-[60%]" title={threadId || ""}>
          {threadId ? `thread_${threadId}` : "thread"}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-primary"
            onClick={onNewThread}
          >
            New Thread
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            onClick={disableThreadLogs ? undefined : onOpenThreadLogs}
            disabled={!!disableThreadLogs}
          >
            Thread Logs
          </Button>
        </div>
      </div>
      <div
        ref={chatContainerRef}
        onScroll={onScroll}
        className="bg-white p-3 flex-1 overflow-y-auto scrollbar-hide"
      >
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
              onPreviewAttachment={(f) => onPreviewAttachment(f)}
            />
          ))}
        </div>
      </div>

      {/* Input Area */}
      <div className="bg-white p-4 pt-0">
        {error && <div className="mb-2 text-sm text-destructive">{error}</div>}

        {selectedFiles.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {selectedFiles.map((file) => (
              <div
                key={file.componentId}
                className="flex items-center gap-2 bg-muted/50 border rounded-lg px-3 py-2 text-sm group hover:border-primary/50 transition-colors"
              >
                <File className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <div className="flex flex-col min-w-0">
                  <span className="font-medium truncate max-w-[200px]" title={file.filename}>
                    {file.filename}
                  </span>
                  <span className="text-xs text-muted-foreground truncate" title={file.componentName}>
                    for {file.componentName}
                  </span>
                </div>
                <div className="flex items-center gap-1 ml-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onPreviewFile(file)}
                    className="h-6 w-6 p-0 text-muted-foreground hover:text-primary flex-shrink-0"
                    title="Preview file"
                  >
                    <Eye className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onRemoveSelectedFile(file.componentId)}
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
                ref={textareaRef}
                value={input}
                rows={1}
                onChange={(e) => setInput(e.target.value)}
                onInput={autoResizeTextarea}
                placeholder="Type your message..."
                className="w-full p-3 pr-20 rounded-lg border border-input bg-background text-sm resize-none min-h-[40px] max-h-[200px] overflow-y-auto focus:outline-none focus:ring-1 focus:ring-primary"
                onKeyDown={onKeyPress}
                disabled={isLoading || !!streamingMessageId}
              />

              <div className="absolute right-2 top-1.5 flex items-center gap-1">
                {fileInputComponents.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={isLoading || !!streamingMessageId}
                    className="h-8 w-8 p-0 hover:bg-muted"
                    onClick={onOpenFileModal}
                  >
                    <Upload className="h-4 w-4" />
                  </Button>
                )}

                <button
                  onClick={streamingMessageId ? onStop : onSend}
                  disabled={!streamingMessageId && (!input.trim() || isLoading)}
                  className={`p-2 rounded-md transition-colors ${
                    streamingMessageId
                      ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      : "bg-primary text-primary-foreground hover:bg-primary/90"
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                  aria-label={streamingMessageId ? "Stop generation" : "Submit message"}
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
                onClick={onOpenFileModal}
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
                  onClick={streamingMessageId ? onStop : onSend}
                  disabled={!streamingMessageId && isLoading}
                  className={`px-6 py-2.5 rounded-md transition-colors ${
                    streamingMessageId
                      ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      : "bg-primary text-primary-foreground hover:bg-primary/90"
                  } disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2`}
                  aria-label={streamingMessageId ? "Stop generation" : "Process file"}
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

        {/* Right panel sample files selection */}
        {sampleFileNames.length > 0 && selectedFiles.length === 0 && showSampleSection && (
          <div className="mt-4">
            <p className="text-xs text-[#444] font-medium mb-2">
              Or Choose from Sample Input files below
            </p>
            <div className="flex flex-wrap gap-2">
              {sampleFileNames.map((name, idx) => (
                <div
                  key={`${name}-${idx}`}
                  className="flex items-center gap-2 bg-muted/50 border rounded-lg px-3 py-2 text-sm cursor-pointer hover:bg-muted"
                  onClick={() => onSelectSampleFile(sampleFilePaths[idx])}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      onSelectSampleFile(sampleFilePaths[idx]);
                    }
                  }}
                >
                  <File className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <span className="truncate max-w-[180px]" title={name}>
                    {name}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-1 text-muted-foreground hover:text-primary"
                    onClick={(e) => {
                      e.stopPropagation();
                      onPreviewSampleFile(sampleFilePaths[idx]);
                    }}
                    title="Preview sample file"
                  >
                    Preview Sample
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}