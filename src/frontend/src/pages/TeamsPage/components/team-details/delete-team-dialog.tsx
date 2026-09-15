import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { AuthorizationTeam } from "@/types/authz";

export function DeleteTeamDialog({
  team,
  open,
  onOpenChange,
  loading,
  onDelete,
}: {
  team: AuthorizationTeam;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  loading: boolean;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {t("teams.deleteConfirmTitle", { teamName: team.team_name })}
          </DialogTitle>
          <DialogDescription>
            {t("teams.deleteConfirmDescription")}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            {t("teams.cancel")}
          </Button>
          <Button
            type="button"
            variant="destructive"
            loading={loading}
            onClick={onDelete}
          >
            {t("teams.deleteConfirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
