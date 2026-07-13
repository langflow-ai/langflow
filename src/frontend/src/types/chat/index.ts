import type { FlowType } from "../flow";

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
  flow_id?: string;
  session_id?: string;
  sender?: string;
  sender_name?: string;
  text?: string | number;
  background_color?: string;
  text_color?: string;
  stream_url?: string | null;
  session?: string;
  edit?: boolean;
  icon?: string;
  category?: string;
  properties?: PropertiesType;
  content_blocks?: ContentBlockItem[];
};

export type SourceType = {
  id: string;
  display_name: string;
  source: string;
};

export type UsageType = {
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
};

export type PropertiesType = {
  source?: SourceType;
  icon?: string;
  background_color?: string;
  text_color?: string;
  targets?: string[];
  edited?: boolean;
  allow_markdown?: boolean;
  state?: string;
  positive_feedback?: boolean | null;
  build_duration?: number | null;
  usage?: UsageType | null;
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
  data: {
    artifacts: Record<string, JSONValue>;
    results: JSONValue | ChatOutputType | ChatInputType;
  };
  id: string;
};

// Base content type
export interface BaseContent {
  type: string;
  // Optional stable identity carried across re-emissions of the same logical
  // block. Set by producers that have a natural id (e.g. LangChain
  // tool_call_id). Consumers fall back to position-derived dedup when absent.
  id?: string;
  duration?: number;
  header?: {
    title?: string;
    icon?: string;
  };
  // Nested content. Leaf types leave this empty; container-shaped types
  // (ContentBlock, multimodal ToolContent, multi-step ReasoningContent)
  // populate it. Typed as ContentBlockItem so nested ContentBlock groups
  // are allowed, matching the backend's discriminated union.
  contents?: ContentBlockItem[];
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
  data: Record<string, JSONValue>;
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
  // The backend serializes this field as `tool_input` by default but
  // emits it under the `input` alias when AG-UI / any other path runs
  // model_dump with by_alias=True. Accept both shapes; renderers should
  // prefer `tool_input` and fall back to `input`.
  tool_input?: Record<string, JSONValue>;
  input?: Record<string, JSONValue>;
  output?: JSONValue;
  error?: JSONValue | string;
}

export interface ImageContent extends BaseContent {
  type: "image";
  urls?: string[];
  base64?: string;
  mime_type?: string;
  caption?: string;
}

export interface AudioContent extends BaseContent {
  type: "audio";
  urls?: string[];
  base64?: string;
  mime_type?: string;
  duration?: number;
  transcript?: string;
}

export interface VideoContent extends BaseContent {
  type: "video";
  urls?: string[];
  base64?: string;
  mime_type?: string;
  duration?: number;
}

export interface FileContent extends BaseContent {
  type: "file";
  urls?: string[];
  mime_type?: string;
  filename?: string;
}

export interface ReasoningContent extends BaseContent {
  type: "reasoning";
  text: string;
}

export interface UsageContent extends BaseContent {
  type: "usage";
  input_tokens?: number;
  output_tokens?: number;
  model?: string;
}

export interface CitationContent extends BaseContent {
  type: "citation";
  url?: string;
  title?: string;
  cited_text?: string;
  start_index?: number;
  end_index?: number;
}

// Union type for all content types
export type ContentType =
  | ErrorContent
  | TextContent
  | MediaContent
  | JSONContent
  | CodeContent
  | ToolContent
  | ImageContent
  | AudioContent
  | VideoContent
  | FileContent
  | ReasoningContent
  | UsageContent
  | CitationContent;

// A titled group of nested contents. Matches the backend's ContentBlock,
// which is a member of the ContentType discriminated union with tag "group".
// Extends BaseContent so it inherits id/header/duration alongside the
// group-specific fields.
export interface ContentBlock extends BaseContent {
  type: "group";
  title: string;
  contents: ContentBlockItem[];
  // Optional to match the backend default (True) and to tolerate hand-built
  // or legacy payloads that don't include the field.
  allow_markdown?: boolean;
  media_url?: string[];
  // Legacy field kept for backwards compatibility with older callers.
  component?: string;
}

// A content block item can be either a grouped ContentBlock or a flat ContentType
export type ContentBlockItem = ContentType | ContentBlock;

// Type guard for grouped ContentBlock items. Prefers the discriminator
// `type === "group"` (new payloads). Falls back to a structural check ONLY
// when `type` is absent, so legacy ContentBlock dicts persisted before the
// discriminator existed (no `type`, only title + contents) are still
// classified as groups. The fallback must not fire on flat ContentType
// items that happen to carry a `title` (CodeContent, CitationContent) and
// an empty inherited `contents: []` -- backend BaseContent serializes
// contents on every item, so the type check is what keeps them out.
export function isGroupedBlock(item: ContentBlockItem): item is ContentBlock {
  if (item.type === "group") return true;
  if (item.type) return false;
  return (
    "title" in item &&
    "contents" in item &&
    Array.isArray((item as { contents?: unknown }).contents)
  );
}

export interface PlaygroundEvent {
  event_type: "message" | "error" | "warning" | "info" | "token";
  background_color?: string;
  text_color?: string;
  allow_markdown?: boolean;
  icon?: string | null;
  sender_name: string;
  content_blocks?: ContentBlockItem[] | null;
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

// JSON-serializable value type
export type JSONValue =
  | string
  | number
  | boolean
  | null
  | JSONValue[]
  | { [key: string]: JSONValue };

// Generic JSON object helper
export type JSONObject = Record<string, JSONValue>;
