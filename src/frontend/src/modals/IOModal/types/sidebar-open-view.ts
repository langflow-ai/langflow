import type { SessionsPagination } from "@/components/core/playgroundComponent/chat-view/chat-header/components/show-more-sessions";

export type SidebarOpenViewProps = {
  sessions: string[];
  sessionsPagination: SessionsPagination;
  setSelectedViewField: (
    field: { type: string; id: string } | undefined,
  ) => void;
  setvisibleSession: (session: string | undefined) => void;
  handleDeleteSession: (session: string) => void;
  visibleSession: string | undefined;
  selectedViewField: { type: string; id: string } | undefined;
  playgroundPage: boolean;
  setActiveSession: (session: string) => void;
};
