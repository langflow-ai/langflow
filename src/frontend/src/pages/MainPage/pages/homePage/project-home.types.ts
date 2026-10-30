import type { ReactNode } from "react";
import type { FlowType } from "@/types/flow";
import type { FlowTabType } from "../../types";

export interface CustomProjectHomeProps {
  children: ReactNode;
  description: string;
  flowType: FlowTabType;
  flows: FlowType[];
  folderDisplayName: string;
  folderName: string;
  isLoading: boolean;
  onNewFlow: () => void;
  onSearch: (search: string) => void;
  setFlowType: (flowType: FlowTabType) => void;
}
