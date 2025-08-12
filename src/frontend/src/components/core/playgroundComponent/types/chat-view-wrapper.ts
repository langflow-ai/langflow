export type ChatViewWrapperProps = {
  selectedViewField: { type: string; id: string } | undefined;
  visibleSession: string | undefined;
  messagesFetched: boolean;
  sessionId: string;
  sendMessage: (options: { repeat: number; files?: string[] }) => Promise<void>;
  playgroundPage?: boolean;
};
