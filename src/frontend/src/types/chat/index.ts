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
