export type CustomShareResourceType =
  | "deployment"
  | "project"
  | "knowledge_base"
  | "file";

export type CustomShareResourceSubtype = "knowledge_base" | "memory";

export interface CustomResourceShareActionProps {
  resourceId: string;
  resourceType: CustomShareResourceType;
  resourceSubtype?: CustomShareResourceSubtype;
  resourceName?: string;
  /** Compact actions use only an icon; headers may request a text label. */
  display?: "icon" | "label" | "menu";
}

// OSS no-op. Enterprise replaces this seam with share administration for
// non-flow resources while preserving the OSS navigation and action layouts.
export default function CustomResourceShareAction(
  _: CustomResourceShareActionProps,
) {
  return null;
}
