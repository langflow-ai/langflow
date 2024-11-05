import { FlowType } from "../flow";

export type ChatType = { flow: FlowType };
export type ChatMessageType = {
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
};

export type ChatOutputType = {
  message: string;
  sender: string;
  sender_name: string;
  stream_url?: string;
  files?: Array<{ path: string; type: string; name: string }>;
};

export type ChatInputType = {
  message: string;
  sender: string;
  sender_name: string;
  stream_url?: string;
  files?: Array<{ path: string; type: string; name: string }>;
};

export type FlowPoolObjectType = {
  timestamp: string;
  valid: boolean;
  // list of chat outputs or list of chat inputs
  messages: Array<ChatOutputType | ChatInputType> | [];
  data: { artifacts: any; results: any | ChatOutputType | ChatInputType };
  id: string;
};

// Base content type
export interface BaseContent {
  type: string;
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

export interface ToolStartContent extends BaseContent {
  type: "tool_start";
  tool_name: string;
  tool_input: Record<string, any>;
}

export interface ToolEndContent extends BaseContent {
  type: "tool_end";
  tool_name: string;
  tool_output: any;
}

export interface ToolErrorContent extends BaseContent {
  type: "tool_error";
  tool_name: string;
  tool_error: string;
}

// Union type for all content types
export type ContentType =
  | ErrorContent
  | TextContent
  | MediaContent
  | JSONContent
  | CodeContent
  | ToolStartContent
  | ToolEndContent
  | ToolErrorContent;

// Updated ContentBlock interface
export interface ContentBlock {
  title: string;
  content: ContentType;
  allow_markdown: boolean;
  media_url?: string[];
  component: string;
}

export interface PlaygroundEvent {
  event_type: "message" | "error" | "warning" | "info" | "token";
  background_color?: string;
  text_color?: string;
  allow_markdown?: boolean;
  icon?: string | null;
  sender_name: string;
  content_blocks?: ContentBlock[] | null;
  files?: string[];
  text?: string;
  timestamp?: string;
  token?: string;
  id?: string;
  flow_id?: string;
  sender?: string;
  session_id?: string;
  edit?: boolean;
}
