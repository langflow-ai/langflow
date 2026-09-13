import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { usePermissions } from "@/contexts/permissionsContext";
import { useGetAuthorizationCapabilities } from "@/controllers/API/queries/authorization";

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
  onShare?: () => void;
}

function ProjectResourceShareAction({
  resourceId,
  resourceName,
  display = "menu",
  onShare,
}: CustomResourceShareActionProps) {
  const { t } = useTranslation();
  const { capability, isUnavailable } = usePermissions();
  const capabilities = useGetAuthorizationCapabilities();
  const supported = Boolean(
    capabilities.data?.enforcement_active &&
      capabilities.data.service_ready &&
      capabilities.data.user_team_sharing_supported,
  );
  if (
    isUnavailable ||
    !supported ||
    !capability(resourceId, "can_manage_shares")
  ) {
    return null;
  }

  if (!onShare) return null;

  return display === "menu" ? (
    <DropdownMenuItem
      className="cursor-pointer text-xs"
      data-testid={`share-project-${resourceId}`}
      onSelect={onShare}
    >
      <ForwardedIconComponent
        name="Share2"
        aria-hidden="true"
        className="mr-2 h-4 w-4"
      />
      {t("misc.share")}
    </DropdownMenuItem>
  ) : (
    <Button
      type="button"
      variant="ghost"
      size={display === "icon" ? "icon" : "sm"}
      aria-label={t("sharing.action.for", { resource: resourceName })}
      onClick={onShare}
    >
      <ForwardedIconComponent name="Share2" aria-hidden="true" />
      {display === "label" ? t("misc.share") : null}
    </Button>
  );
}

export default function CustomResourceShareAction(
  props: CustomResourceShareActionProps,
) {
  if (props.resourceType !== "project") return null;
  return <ProjectResourceShareAction {...props} />;
}
