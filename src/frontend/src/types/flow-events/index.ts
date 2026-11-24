type FlowEventType =
  | "component_added"
  | "component_removed"
  | "component_configured"
  | "connection_added"
  | "connection_removed"
  | "flow_updated"
  | "flow_settled";

export type FlowEvent = {
  type: FlowEventType;
  timestamp: number;
  summary: string;
};

export type FlowEventsResponse = {
  events: FlowEvent[];
  settled: boolean;
};
