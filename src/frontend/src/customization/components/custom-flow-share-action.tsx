import type { PermissionResourceType } from "@/types/permissions";

interface CustomFlowShareActionProps {
  resourceId: string;
  resourceType: PermissionResourceType;
  resourceName?: string;
}

// OSS no-op; the Enterprise overlay replaces this with the Share menu item + dialog.
export default function CustomFlowShareAction(_: CustomFlowShareActionProps) {
  return null;
}
