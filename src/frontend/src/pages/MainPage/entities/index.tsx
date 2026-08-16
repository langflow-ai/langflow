import type { FlowType } from "../../../types/flow";

export type FolderType = {
  name: string;
  description: string;
  id?: string | null;
  parent_id: string;
  flows: FlowType[];
  components: string[];
  owner_username?: string | null;
  is_owner?: boolean;
};

export type ProjectListType = FolderType & {
  id: string;
  owner_username: string | null;
  is_owner: boolean;
};

export type PaginatedFolderType = {
  folder: {
    name: string;
    description: string;
    id?: string | null;
    parent_id: string;
    components: string[];
  };
  flows: {
    items: FlowType[];
    total: number;
    page: number;
    size: number;
    pages: number;
  };
};

export type AddFolderType = {
  name: string;
  description: string;
  id?: string | null;
  parent_id: string | null;
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
