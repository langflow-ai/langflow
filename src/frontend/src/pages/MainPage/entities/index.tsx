import { FlowType } from "../../../types/flow";

export type FolderType = {
  name: string;
  description: string;
  id?: string | null;
  parent_id: string;
  flows: FlowType[];
};

export type AddFolderType = {
  name: string;
  description: string;
  id?: string | null;
  parent_id: string;
  flows?: string[];
  components?: string[];
};

export type StarterProjectsType = {
  name?: string;
  description?: string;
  flows?: FlowType[];
  id: string;
  parent_id: string;
};
