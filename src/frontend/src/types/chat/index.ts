import { FlowType } from "../flow";

export type ChatType = { flow: FlowType };
export type ChatMessageType = {
  message: string | Object;
  template?: string;
  isSend: boolean;
  thought?: string;
  files?: Array<{ data: string; type: string; data_type: string }>;
  prompt?: string;
  chatKey?: string;
  componentId: string;
  stream_url?: string | null;
  sender_name?: string;
};

export type ChatOutputType = {
  message: string;
  sender: string;
  sender_name: string;
  stream_url?: string;
};

export type chatInputType = {
  result: string;
};

export type FlowPoolObjectType = {
  timestamp: string;
  valid: boolean;
  params: any;
  data: { artifacts: any; results: any | ChatOutputType | chatInputType };
  id: string;
};
