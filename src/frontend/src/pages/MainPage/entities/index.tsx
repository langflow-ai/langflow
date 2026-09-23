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

/**
 * What a save returns: the project row, plus what the save did beyond it.
 *
 * `flows_updated` counts the flows the project's form was written into, so the UI can say what
 * actually happened rather than only that the row was stored.
 */
export type ProjectSaveResult = FolderType & {
  flows_updated?: number;
  fields_skipped?: number;
  flows_locked?: number;
  restore_version_ids?: Record<string, string>;
};

/** A reusable flow contract. Its presence does not imply a custom flow can already run. */
export type FlowContract = {
  name: string;
  terminal_output_type: string;
  fire_timing: string;
  cardinality: "single" | "multi";
  default_flow_ref: string | null;
};

export type FlowBinding = {
  flow_id: string;
  node_id: string;
  output_name: string;
  revision: string;
  version_id?: string | null;
};

export type FlowOutputChoice = FlowBinding & {
  flow_name: string;
  display_name: string;
};

export type ContextBinding = FlowBinding & { timeout_seconds?: number };
export type CompactionBinding = ContextBinding & { trigger_tokens?: number };

export type HookEvent =
  | "before_llm_call"
  | "after_llm_call"
  | "before_tool_call"
  | "after_tool_call";
export type HookBinding = FlowBinding & {
  on_event: HookEvent;
  priority?: number;
  mode?: "observe" | "control";
  timeout_seconds?: number;
  on_failure?: "continue" | "stop";
};
export type ProjectFlowBindings = Record<
  string,
  FlowBinding | ContextBinding | CompactionBinding | HookBinding[] | undefined
>;

/** A project type and the form it renders, from `GET /api/v1/projects/types`. */
export type ProjectTypeType = {
  starters?: { name: string; display_name: string; description: string }[];
  name: string;
  display_name: string;
  icon: string;
  description: string;
  /** Keyed by field name, in the same shape as a component's template. */
  template: Record<
    string,
    Partial<InputFieldType> & {
      renders?: string;
      section?: string;
      flow_contract?: FlowContract;
      supports_flow_binding?: boolean;
      show_when?: Record<string, string>;
      option_labels?: Record<string, string>;
    }
  >;
};

export type StarterProjectsType = {
  name?: string;
  description?: string;
  flows?: FlowType[];
  id: string;
  parent_id: string;
};
