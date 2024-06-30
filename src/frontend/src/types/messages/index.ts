type Message = {
  artifacts: Record<string, any>;
  flow_id: string;
  message: string;
  sender: string;
  sender_name: string;
  session_id: string;
  timestamp: string;
  files: Array<string>;
  id: string;
};

export type { Message };
