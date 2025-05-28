import { Node } from "reactflow";
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
  nodes: Node[];
};
