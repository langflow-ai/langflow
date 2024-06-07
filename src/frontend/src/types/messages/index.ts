type Message = {
  artifacts: Record<string, any>;
  flow_id: string;
  index: number;
  message: string;
  sender: string;
  sender_name: string;
  session_id: string;
  timestamp: string;
  id: string;
};

export type { Message };
