/* eslint-disable @typescript-eslint/no-explicit-any */
export type ChatViewWrapperProps = {
    selectedViewField: { type: string; id: string } | undefined;
    visibleSession: string | undefined;
    sessions: string[];
    sidebarOpen: boolean;
    currentFlowId: string;
    setSidebarOpen: (open: boolean) => void;
    setvisibleSession: (session: string | undefined) => void;
    setSelectedViewField: (
      field: { type: string; id: string } | undefined,
    ) => void;
    haveChat: { type: string; id: string; displayName: string } | undefined;
    messagesFetched: boolean;
    sessionId: string;
    sendMessage: (options: { repeat: number; files?: string[] }) => Promise<void>;
    lockChat: boolean;
    setLockChat: (locked: boolean) => void;
  };

  export type chatViewProps = {
    sendMessage: ({
      repeat,
      files,
    }: {
      repeat: number;
      files?: string[];
    }) => void;
    lockChat: boolean;
    setLockChat: (lock: boolean) => void;
    visibleSession?: string;
    focusChat?: string;
    closeChat?: () => void;
    inputs: any[];
  };

  export type SourceType = {
    id: string;
    display_name: string;
    source: string;
  };

  export type PropertiesType = {
    source: SourceType;
    icon?: string;
    background_color?: string;
    text_color?: string;
    targets?: string[];
    edited?: boolean;
    allow_markdown?: boolean;
    state?: string;
    positive_feedback?: boolean | null;
  };


  // Base content type
export interface BaseContent {
  type: string;
  duration?: number;
  header?: {
    title?: string;
    icon?: string;
  };
}

// Individual content types
export interface ErrorContent extends BaseContent {
  type: "error";
  component?: string;
  field?: string;
  reason?: string;
  solution?: string;
  traceback?: string;
}

export interface TextContent extends BaseContent {
  type: "text";
  text: string;
}

export interface MediaContent extends BaseContent {
  type: "media";
  urls: string[];
  caption?: string;
}

export interface JSONContent extends BaseContent {
  type: "json";
  data: Record<string, any>;
}

export interface CodeContent extends BaseContent {
  type: "code";
  code: string;
  language: string;
  title?: string;
}

export interface ToolContent extends BaseContent {
  type: "tool_use";
  name?: string;
  tool_input: Record<string, any>;
  output?: any;
  error?: any;
}

  // Union type for all content types
export type ContentType =
| ErrorContent
| TextContent
| MediaContent
| JSONContent
| CodeContent
| ToolContent;

// Updated ContentBlock interface
export interface ContentBlock {
title: string;
contents: ContentType[];
allow_markdown: boolean;
media_url?: string[];
component: string;
}


  export type ChatMessageType = {
    // eslint-disable-next-line @typescript-eslint/no-wrapper-object-types
    message: string | Object;
    template?: string;
    isSend: boolean;
    thought?: string;
    files?: Array<{ path: string; type: string; name: string } | string>;
    prompt?: string;
    chatKey?: string;
    componentId?: string;
    id: string;
    timestamp: string;
    stream_url?: string | null;
    sender_name?: string;
    session?: string;
    edit?: boolean;
    icon?: string;
    category?: string;
    properties?: PropertiesType;
    content_blocks?: ContentBlock[];
  };
