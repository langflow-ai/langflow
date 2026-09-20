import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Switch } from "@/components/ui/switch";
import type { ConnectionRead } from "@/controllers/API/queries/connections";

export interface ConnectionRowMenuProps {
  connection: ConnectionRead;
  /** Only the owner (a superuser, for an instance row) may widen unattended use. */
  canAllowUnattended: boolean;
  busy: boolean;
  onTest: (connection: ConnectionRead) => void;
  onAuthorize: (connection: ConnectionRead) => void;
  onRename: (connection: ConnectionRead) => void;
  onToggleUnattended: (connection: ConnectionRead, next: boolean) => void;
  onRevoke: (connection: ConnectionRead) => void;
  onDelete: (connection: ConnectionRead) => void;
}

export function ConnectionRowMenu({
  connection,
  canAllowUnattended,
  busy,
  onTest,
  onAuthorize,
  onRename,
  onToggleUnattended,
  onRevoke,
  onDelete,
}: ConnectionRowMenuProps) {
  const { t } = useTranslation();
  const { status } = connection;
  // Delete only once the credential is gone, so nothing is orphaned at the provider.
  const canDelete = status === "pending" || status === "revoked";
  const canRevoke = connection.has_credentials && status !== "revoked";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="iconMd"
          disabled={busy}
          aria-label={t("connections.actions.menu", {
            name: connection.display_name,
          })}
          data-testid={`connection-menu-${connection.name}`}
        >
          <ForwardedIconComponent name="Ellipsis" className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[16rem]">
        <DropdownMenuItem
          disabled={!connection.has_credentials}
          onSelect={() => onTest(connection)}
        >
          <ForwardedIconComponent name="Activity" className="mr-2 h-4 w-4" />
          {t("connections.actions.test")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => onAuthorize(connection)}>
          <ForwardedIconComponent name="RefreshCw" className="mr-2 h-4 w-4" />
          {status === "pending"
            ? t("connections.actions.authorize")
            : t("connections.actions.reauthorize")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => onRename(connection)}>
          <ForwardedIconComponent name="Pencil" className="mr-2 h-4 w-4" />
          {t("connections.actions.rename")}
        </DropdownMenuItem>
        <DropdownMenuItem
          // Keep the menu open while the switch toggles.
          onSelect={(event) => event.preventDefault()}
          className="flex items-center justify-between gap-4"
        >
          <span className="flex items-center">
            <ForwardedIconComponent name="Clock" className="mr-2 h-4 w-4" />
            {t("connections.actions.allowUnattended")}
          </span>
          <Switch
            checked={connection.allow_non_interactive}
            // Anyone who may write can withdraw it; only the owner grants it.
            disabled={
              busy || (!connection.allow_non_interactive && !canAllowUnattended)
            }
            aria-label={t("connections.actions.allowUnattended")}
            onCheckedChange={(next) => onToggleUnattended(connection, next)}
            data-testid={`unattended-${connection.name}`}
          />
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={!canRevoke}
          onSelect={() => onRevoke(connection)}
        >
          <ForwardedIconComponent name="Unplug" className="mr-2 h-4 w-4" />
          {t("connections.actions.revoke")}
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={!canDelete}
          className="text-destructive focus:text-destructive"
          onSelect={() => onDelete(connection)}
        >
          <ForwardedIconComponent name="Trash2" className="mr-2 h-4 w-4" />
          {t("connections.actions.delete")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default ConnectionRowMenu;
