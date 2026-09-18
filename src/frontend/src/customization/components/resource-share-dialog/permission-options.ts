import type { ShareDialogPermission } from "@/types/authz";

export const permissionOptions: ShareDialogPermission[] = ["execute", "write"];

export function permissionLabelKey(permission: ShareDialogPermission) {
  return permission === "execute"
    ? "sharing.mode.use.label"
    : "sharing.mode.edit.label";
}

export function permissionDescriptionKey(permission: ShareDialogPermission) {
  return permission === "execute"
    ? "sharing.mode.use.description"
    : "sharing.mode.edit.description";
}

export function preservedPermissionLabelKey(permission: "read" | "admin") {
  return permission === "read"
    ? "sharing.mode.read.label"
    : "sharing.mode.admin.label";
}

export function preservedPermissionDescriptionKey(
  permission: "read" | "admin",
) {
  return permission === "read"
    ? "sharing.mode.read.description"
    : "sharing.mode.admin.description";
}
