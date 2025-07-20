import type { ContentBlock } from "../chat";

type Message = {
  flow_id: string;
  text: string;
  sender: string;
  sender_name: string;
  session_id: string;
  timestamp: string;
  files: Array<string>;
  id: string;
  edit: boolean;
  background_color: string;
  text_color: string;
  category?: string;
  properties?: any;
  content_blocks?: ContentBlock[];
};

export type { Message };
