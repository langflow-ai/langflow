import { FlowType } from "../../../types/flow";

export type FolderType = {
  name: string;
  description: string;
  id?: string | null;
  parent_id: string;
  flows: FlowType[];
};
