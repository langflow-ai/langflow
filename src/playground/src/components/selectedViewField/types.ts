export type SelectedViewFieldProps = {
  selectedViewField: { type: string; id: string } | undefined;
  setSelectedViewField: (
    field: { type: string; id: string } | undefined,
  ) => void;
  haveChat: { type: string; id: string; displayName: string } | undefined;
  inputs: Array<{
    type: string;
    id: string;
    displayName: string;
  }>;
  outputs: Array<{
    type: string;
    id: string;
    displayName: string;
  }>;
  sessions: string[];
  currentFlowId: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  nodes: any[];
};
