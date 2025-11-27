import { useState, useMemo, useEffect, useRef } from "react";
import { FileUploadManager } from "./FileUploadManager";
import { FilePreviewModal } from "./FilePreviewModal";
import { SampleTextModal } from "./SampleTextModal";
import {
  PlaygroundTabProps,
  Message,
  FileInputComponent,
} from "./Playground.types";
import { DragIcon } from "@/assets/icons/DragIcon";
import { usePlaygroundChat } from "./PlaygroundChat";
import { useResizablePanel } from "./UseResizablePanel";
import { usePostReadPresignedUrl } from "@/controllers/API/queries/flexstore";
import { AgentDetailsPanel } from "./AgentDetailsPanel";
import { ChatArea } from "./ChatArea";
import { useThreadManager } from "./ThreadManager";
import ThreadLogsDrawer from "./ThreadLogsDrawer";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
// Removed ThreadLogsModal in favor of the new ThreadLogsDrawer

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
  const [showSampleSection, setShowSampleSection] = useState(true);
  const [sampleTextModal, setSampleTextModal] = useState<{
    isOpen: boolean;
    text: string;
    index: number;
    title?: string;
  }>({
    isOpen: false,
    text: "",
    index: 0,
  });

  // Refs for auto-scroll and input focus
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isUserScrollingRef = useRef(false);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-resize textarea up to a maximum height, then enable scroll
  const MAX_TEXTAREA_HEIGHT = 200; // pixels
  const autoResizeTextarea = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const newHeight = Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT);
    el.style.height = `${newHeight}px`;
    el.style.overflowY =
      el.scrollHeight > MAX_TEXTAREA_HEIGHT ? "auto" : "hidden";
  };

  const { leftPanelWidth, isDragging, handleDragStart } =
    useResizablePanel(33.33);

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
    sessionId,
    setSessionId,
    clearConversation,
  } = usePlaygroundChat(publishedFlowData);

  // Thread management
  const { currentThreadId, newThread } = useThreadManager();
  const [isThreadLogsOpen, setIsThreadLogsOpen] = useState(false);
  const [isConfirmNewThreadOpen, setIsConfirmNewThreadOpen] = useState(false);

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
    // Prefer flow_name from published flow API; fallback to name
    name: publishedFlowData?.flow_name || publishedFlowData?.name || "Agent",
  };

  const sampleFilePaths: string[] = Array.isArray(
    publishedFlowData?.input_samples
  )
    ? publishedFlowData!.input_samples.flatMap((s: any) =>
        Array.isArray(s?.file_names) ? s.file_names : []
      )
    : [];

  const sampleFileNames: string[] = sampleFilePaths.map((path: string) => {
    try {
      const idx = path.lastIndexOf("/");
      return idx >= 0 ? path.slice(idx + 1) : path;
    } catch {
      return String(path);
    }
  });

  // Aggregate sample input texts from input_samples
  const sampleTexts: string[] = Array.isArray(publishedFlowData?.input_samples)
    ? publishedFlowData!.input_samples.flatMap((s: any) =>
        Array.isArray(s?.sample_text) ? s.sample_text : []
      )
    : [];

  // Helper to safely stringify JSON-like values
  const stringifyIfObject = (val: any): string | undefined => {
    if (val === undefined || val === null) return undefined;
    if (typeof val === "string") return val;
    try {
      return JSON.stringify(val, null, 2);
    } catch {
      return String(val);
    }
  };

  // First available sample output across input_samples (supports object or string)
  const sampleOutput: string | undefined = Array.isArray(
    publishedFlowData?.input_samples
  )
    ? (() => {
        const found = publishedFlowData!.input_samples.find(
          (s: any) => s && s.sample_output
        );
        return stringifyIfObject(found?.sample_output);
      })()
    : undefined;

  // Helper to open sample text modal
  const openSampleTextModal = (text: string, index: number, title?: string) => {
    setSampleTextModal({
      isOpen: true,
      text,
      index,
      title,
    });
  };

  // Helper to close sample text modal
  const closeSampleTextModal = () => {
    setSampleTextModal({
      isOpen: false,
      text: "",
      index: 0,
    });
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
        const extension = filename.split(".").pop()?.toLowerCase() || "";
        let fileType = "application/octet-stream";

        if (extension === "json") fileType = "application/json";
        else if (extension === "png") fileType = "image/png";
        else if (extension === "pdf") fileType = "application/pdf";

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

  // Auto-scroll functionality
  const scrollToBottom = (smooth: boolean = true) => {
    if (chatContainerRef.current && !isUserScrollingRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: smooth ? "smooth" : "auto",
      });
    }
  };

  // Detect user manual scrolling
  const handleScroll = () => {
    if (!chatContainerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;

    // If user scrolls up, mark as user scrolling
    if (!isNearBottom) {
      isUserScrollingRef.current = true;

      // Clear existing timeout
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }

      // Reset user scrolling flag after 2 seconds of no scrolling
      scrollTimeoutRef.current = setTimeout(() => {
        isUserScrollingRef.current = false;
      }, 2000);
    } else {
      isUserScrollingRef.current = false;
    }
  };

  // Auto-scroll when messages change or streaming updates
  useEffect(() => {
    scrollToBottom(true);
  }, [messages, displayedTexts]);

  // Auto-resize textarea on mount and whenever input changes
  useEffect(() => {
    autoResizeTextarea();
  }, [input]);

  // Focus input after sending message
  const focusInput = () => {
    if (textareaRef.current && hasChatInput) {
      // Small delay to ensure DOM updates are complete
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 100);
    }
  };

  const sendMessage = async () => {
    if (hasChatInput && !input.trim() && selectedFiles.length === 0) return;
    if (!hasChatInput && selectedFiles.length === 0) return;
    if (isLoading) return;

    const currentFileUrls = { ...fileUrls };
    const messageText = input.trim() || "";

    const attachments = selectedFiles.map((file) => ({
      url: file.url,
      name: file.filename,
      type: file.fileType,
    }));

    setShowSampleSection(false);
    setFileUrls({});
    setInput("");

    isUserScrollingRef.current = false;

    await sendMessageHook(
      messageText,
      currentFileUrls,
      fileInputComponents,
      attachments
    );

    focusInput();
  };

  const performNewThread = () => {
    const nextId = newThread(messages.length);
    clearConversation();
    setSessionId(nextId);
    setShowSampleSection(true);
  };

  const handleNewThread = () => {
    setIsConfirmNewThreadOpen(true);
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleFileUrlChange = (componentId: string, url: string) => {
    setShowSampleSection(false);
    setFileUrls((prev) => ({
      ...prev,
      [componentId]: url,
    }));
  };

  const clearFileUrl = (componentId: string) => {
    setShowSampleSection(false);
    setFileUrls((prev) => {
      const newUrls = { ...prev };
      delete newUrls[componentId];
      return newUrls;
    });
  };

  const removeSelectedFile = (componentId: string) => {
    setShowSampleSection(false);
    clearFileUrl(componentId);
  };

  const handlePreviewFile = (file: (typeof selectedFiles)[0]) => {
    setPreviewFile({
      url: file.url,
      name: file.filename,
      type: file.fileType,
    });
  };

  const readPresignedUrlMutation = usePostReadPresignedUrl();

  const getFileTypeFromName = (name: string) => {
    const ext = name.split(".").pop()?.toLowerCase() || "";
    if (ext === "json") return "application/json";
    if (ext === "png") return "image/png";
    if (ext === "jpg" || ext === "jpeg") return "image/jpeg";
    if (ext === "pdf") return "application/pdf";
    return "application/octet-stream";
  };

  const getStorageDetails = () => {
    const sample0 = Array.isArray(publishedFlowData?.input_samples)
      ? publishedFlowData!.input_samples[0]
      : undefined;
    const containerName = sample0?.container_name || "ai-studio-v2";
    const storageAccount =
      sample0?.storage_account ||
      process.env.FLEXSTORE_DEFAULT_STORAGE_ACCOUNT ||
      "autonomizestorageaccount";
    return { containerName, storageAccount };
  };

  const previewSampleFile = async (filePathOrName: string) => {
    try {
      const { containerName, storageAccount } = getStorageDetails();
      const resp = await readPresignedUrlMutation.mutateAsync({
        sourceType: "azureBlob",
        fileName: filePathOrName,
        sourceDetails: { containerName, storageAccount },
      });
      const signedUrl = resp?.presignedUrl?.data?.signedUrl || "";
      if (!signedUrl) return;
      const name = filePathOrName.includes("/")
        ? filePathOrName.split("/").pop() || filePathOrName
        : filePathOrName;
      const type = getFileTypeFromName(name);
      setPreviewFile({ url: signedUrl, name, type });
    } catch (e) {}
  };

  const selectSampleFile = async (filePathOrName: string) => {
    try {
      const { containerName, storageAccount } = getStorageDetails();
      const resp = await readPresignedUrlMutation.mutateAsync({
        sourceType: "azureBlob",
        fileName: filePathOrName,
        sourceDetails: { containerName, storageAccount },
      });
      const signedUrl = resp?.presignedUrl?.data?.signedUrl || "";
      if (!signedUrl || fileInputComponents.length === 0) return;
      const targetComponentId = fileInputComponents[0].id;
      setShowSampleSection(false);
      setFileUrls({ [targetComponentId]: signedUrl });
    } catch (e) {}
  };

  useEffect(() => {
    if (!isLoading && !streamingMessageId && selectedFiles.length === 0) {
      setShowSampleSection(true);
    }
  }, [isLoading, streamingMessageId, selectedFiles.length]);

  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);

  return (
    <div className="flex h-full w-full flex-col ">
      <div
        className={`flex flex-1 overflow-hidden h-full items-center ${
          isThreadLogsOpen ? "mr-[312px]" : ""
        }`}
      >
        {/* Agent Details Panel */}
        <div
          className="flex flex-col rounded-lg border border-primary-border h-full"
          style={{ width: `${leftPanelWidth}%` }}
        >
          <AgentDetailsPanel
            agentDetails={agentDetails}
            sampleFileNames={sampleFileNames}
            sampleFilePaths={sampleFilePaths}
            sampleTexts={sampleTexts}
            sampleOutput={sampleOutput}
            onPreviewSampleFile={previewSampleFile}
            onOpenSampleText={(text, idx) => openSampleTextModal(text, idx)}
            onOpenSampleOutput={(text) =>
              openSampleTextModal(text, 0, "Sample Output")
            }
          />
        </div>

        {/* Drag Handle */}
        <div
          className="w-3 h-[28px] bg-background-surface cursor-col-resize rounded-[4px] text-menu flex items-center justify-center"
          onMouseDown={handleDragStart}
        >
          <DragIcon />
        </div>

        {/* Chat Panel */}
        <div
          className="h-full flex flex-col"
          style={{
            width: `${100 - leftPanelWidth}%`,
            pointerEvents: isDragging ? "none" : "auto",
          }}
        >
          <ChatArea
            messages={messages}
            displayedTexts={displayedTexts}
            targetTexts={targetTexts}
            loadingDots={loadingDots}
            onPreviewAttachment={(f) => setPreviewFile(f)}
            onPreviewSampleFile={previewSampleFile}
            threadId={sessionId}
            onNewThread={handleNewThread}
            onOpenThreadLogs={() => setIsThreadLogsOpen(true)}
            disableThreadLogs={false}
            chatContainerRef={chatContainerRef}
            onScroll={handleScroll}
            error={error}
            selectedFiles={selectedFiles}
            onPreviewFile={handlePreviewFile}
            onRemoveSelectedFile={removeSelectedFile}
            hasChatInput={hasChatInput}
            input={input}
            setInput={setInput}
            streamingMessageId={streamingMessageId}
            isLoading={isLoading}
            onSend={sendMessage}
            onStop={stopStreaming}
            fileInputComponents={fileInputComponents}
            onOpenFileModal={() => setIsFileModalOpen(true)}
            textareaRef={textareaRef}
            autoResizeTextarea={autoResizeTextarea}
            onKeyPress={handleKeyPress}
            showSampleSection={showSampleSection}
            sampleFileNames={sampleFileNames}
            sampleFilePaths={sampleFilePaths}
            onSelectSampleFile={selectSampleFile}
          />
        </div>
      </div>

      {isThreadLogsOpen && (
        <div>
          <ThreadLogsDrawer
            isOpen={isThreadLogsOpen}
            onClose={() => setIsThreadLogsOpen(false)}
            // Pass the agent name used in title: flow_name preferred
            nameParam={
              publishedFlowData?.flow_name ||
              publishedFlowData?.name ||
              agentDetails.name
            }
          />
        </div>
      )}

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

      <SampleTextModal
        isOpen={sampleTextModal.isOpen}
        onClose={closeSampleTextModal}
        text={sampleTextModal.text}
        index={sampleTextModal.index}
      />

      <Dialog
        open={isConfirmNewThreadOpen}
        onOpenChange={setIsConfirmNewThreadOpen}
      >
        <DialogContent className="max-w-[650px]">
          <DialogHeader>
            <DialogTitle>
              Are you sure you want to create a new thread?
            </DialogTitle>
          </DialogHeader>
          <div className="my-6">
            <p className="text-secondary-font text-sm">
              This will clear the previous thread and all its messages from the
              view. To save them, copy the content to a separate document before
              creating a new thread.
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsConfirmNewThreadOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                performNewThread();
                setIsConfirmNewThreadOpen(false);
              }}
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
