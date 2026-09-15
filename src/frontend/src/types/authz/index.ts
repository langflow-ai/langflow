export type TeamRole = "admin" | "maintainer" | "user";

export type TeamView = "all" | "member" | "managed" | "directory";

export type ShareResourceType = "flow" | "project";
export type ShareRecipientType = "user" | "team";
export type ShareDialogPermission = "execute" | "write";

export interface AuthorizationCapabilities {
  enforcement_active: boolean;
  service_ready: boolean;
  team_roles_supported: boolean;
  user_team_sharing_supported: boolean;
  share_modes: ShareDialogPermission[];
  conditional_writes_required: boolean;
  can_administer_platform: boolean;
  can_create_team: boolean;
}

export interface AuthorizationRecipient {
  id: string;
  kind: ShareRecipientType;
  display_name: string;
  avatar?: string | null;
}

export interface AuthorizationRecipientPage {
  items: AuthorizationRecipient[];
  has_more: boolean;
  next_offset?: number | null;
}

export interface TeamCapabilities {
  can_update: boolean;
  can_set_active: boolean;
  can_delete: boolean;
  can_add_user_member: boolean;
  can_add_privileged_member: boolean;
  can_change_roles: boolean;
  can_remove_user_member: boolean;
}

export interface AuthorizationTeam {
  id: string;
  team_name: string;
  adom_name: string;
  description?: string | null;
  is_active: boolean;
  inactivation_reason?: "manual" | "no_active_admin" | null;
  created_at: string;
  updated_at: string;
  member_count: number;
  active_member_count: number;
  active_admin_count: number;
  current_user_role?: TeamRole | null;
  capabilities: TeamCapabilities;
}

export interface AuthorizationTeamMember {
  id: string;
  team_id: string;
  user_id: string;
  display_name?: string | null;
  avatar?: string | null;
  source: string;
  role: TeamRole;
  created_at: string;
  updated_at: string;
}

export interface TeamMemberInput {
  user_id: string;
  role: TeamRole;
}

export interface TeamCreateInput {
  team_name: string;
  adom_name: string;
  description?: string | null;
  is_active?: boolean;
  members: TeamMemberInput[];
}

export interface TeamUpdateInput {
  team_name?: string;
  adom_name?: string;
  description?: string | null;
  is_active?: boolean;
  member_upserts?: TeamMemberInput[];
  remove_member_ids?: string[];
}

export interface AuthorizationShare {
  id: string;
  resource_type: ShareResourceType;
  resource_id: string;
  scope: "private" | "team" | "user" | "public";
  target_id?: string | null;
  target_name?: string | null;
  permission_level: "read" | "execute" | "write" | "admin";
  display_mode?: "read" | "use" | "edit" | "admin" | null;
  revision: number;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ShareAccessSource {
  kind: string;
  actions: string[];
  source_id?: string | null;
  label?: string | null;
}

export interface ShareSummary {
  resource_type: ShareResourceType;
  resource_id: string;
  display_name?: string | null;
  subject_user_id: string;
  caller_is_owner: boolean;
  can_manage_shares: boolean;
  direct_grants: AuthorizationShare[];
  effective_access: {
    actions: string[];
    sources: ShareAccessSource[];
  };
  inherited_from_project: boolean;
  additional_access_warning?: string | null;
  legacy_public_access: boolean;
  administrative_grant_present: boolean;
  has_more: boolean;
  next_offset?: number | null;
}

export interface StructuredApiErrorDetail {
  code?: string;
  message?: string;
}
