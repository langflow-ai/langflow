import type { ContentBlock } from "../chat";

type Message = {
  flow_id: string;
  text: string;
  sender: string;
  sender_name: string;
  session_id: string;
  timestamp: string;
  files: Array<string>;
  id: string | null; // null for placeholder messages
  edit: boolean;
  background_color: string;
  text_color: string;
  category?: string;
  properties?: {
    state?: "partial" | "complete";
    source?: { id?: string };
    [key: string]: unknown;
  };
  content_blocks?: ContentBlock[];
};

// Extended type for Message properties that includes all runtime fields
// Used when converting Message to ChatMessageType
type ExtendedMessageProperties = Message["properties"] & {
  source?: {
    id?: string;
    display_name?: string;
    source?: string;
  };
  icon?: string;
  background_color?: string;
  text_color?: string;
  targets?: string[];
  edited?: boolean;
  allow_markdown?: boolean;
  positive_feedback?: boolean | null;
  build_duration?: number | null;
};

export type { Message, ExtendedMessageProperties };
