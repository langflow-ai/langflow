export type SidebarOpenViewProps = {
  sessions: string[];
  setSelectedViewField: (
    field: { type: string; id: string } | undefined,
  ) => void;
  setvisibleSession: (session: string | undefined) => void;
  handleDeleteSession: (session: string) => void;
  visibleSession: string | undefined;
  selectedViewField: { type: string; id: string } | undefined;
};
