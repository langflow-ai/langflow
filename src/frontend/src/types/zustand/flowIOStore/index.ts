export type ChatInputType = {
  result: string;
};

export type ChatOutputType = {
  message: string;
  sender: string;
  sender_name: string;
};

export type FlowPoolObjectType = {
  timestamp: string;
  valid: boolean;
  params: any;
  data: { artifacts: any; results: any | ChatOutputType | ChatInputType };
  id: string;
};

export type FlowPoolType = {
  [key: string]: Array<FlowPoolObjectType>;
};
