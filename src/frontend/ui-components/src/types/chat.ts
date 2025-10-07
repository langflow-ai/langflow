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
