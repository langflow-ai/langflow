// types/playground.types.ts

export interface PlaygroundTabProps {
  publishedFlowData: any;
}

export interface Message {
  id: string;
  type: "user" | "agent";
  text: string;
  timestamp: Date;
  isStreaming?: boolean;
  files?: {
    name: string;
    url: string;
    type: string;
  }[];
  traceId?: string;
  latency?: string;
  tokenCount?: number;
}

export interface FileInputComponent {
  id: string;
  type: string;
  display_name: string;
  inputKey: string;
}

export interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  readUrl: string;
  uploadTimestamp: Date;
}

export interface FileUploadManagerProps {
  isOpen: boolean;
  onClose: () => void;
  fileInputComponents: FileInputComponent[];
  fileUrls: Record<string, string>;
  onFileUrlChange: (componentId: string, url: string) => void;
  onClearFileUrl: (componentId: string) => void;
  onError: (error: string) => void;
}

export interface AgentDetails {
  createdOn: string;
  lastUpdatedOn: string;
  description: string;
  version: string;
  tags: string[];
  name: string;
}

export interface UploadRequest {
  sourceType: string;
  fileName: string;
  sourceDetails: {
    containerName: string;
    storageAccount: string;
  };
}

export interface UploadResponse {
  presignedUrl: {
    data: {
      signedUrl: string;
    };
    status: string;
  };
}