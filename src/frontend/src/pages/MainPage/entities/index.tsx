import type { InputFieldType } from "@/types/api";
import type { FlowType } from "../../../types/flow";

/** What the user picked on a project's form. The values that run live in the flows. */
export type ProjectConfig = Record<string, unknown>;

export type FolderType = {
  name: string;
  description: string;
  id?: string | null;
  parent_id: string;
  flows: FlowType[];
  components: string[];
  owner_username?: string | null;
  is_owner?: boolean;
  project_type?: string;
  project_config?: ProjectConfig | null;
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
    project_type?: string;
    project_config?: ProjectConfig | null;
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
  project_type?: string;
  project_config?: ProjectConfig | null;
};

/** A project type and the form it renders, from `GET /api/v1/projects/types`. */
export type ProjectTypeType = {
  name: string;
  display_name: string;
  icon: string;
  description: string;
  /** Keyed by field name, in the same shape as a component's template. */
  template: Record<string, Partial<InputFieldType>>;
};

export type StarterProjectsType = {
  name?: string;
  description?: string;
  flows?: FlowType[];
  id: string;
  parent_id: string;
};
