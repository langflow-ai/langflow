import { useId, useState } from "react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useCreateAdminUser,
  useUpdateAdminUser,
} from "@/controllers/API/queries/auth/use-user-administration";
import type { Users } from "@/types/api";
import { extractApiErrorMessages } from "@/utils/apiError";

export function UserFormDialog({
  user,
  onClose,
}: {
  user?: Users;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const usernameId = useId();
  const passwordId = useId();
  const [username, setUsername] = useState(user?.username ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const options = {
    onSuccess: onClose,
    onError: (requestError: Error) =>
      setError(extractApiErrorMessages(requestError).join(" ")),
  };
  const create = useCreateAdminUser(options);
  const update = useUpdateAdminUser(options);
  const pending = create.isPending || update.isPending;
  const canSave = Boolean(username.trim() && (user || password));

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !pending) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {t(user ? "adminUsers.editTitle" : "adminUsers.addTitle")}
          </DialogTitle>
          <DialogDescription>
            {t(
              user ? "adminUsers.editDescription" : "adminUsers.addDescription",
            )}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!canSave || pending) return;
            setError(null);
            if (user) {
              update.mutate({
                id: user.id,
                fields: {
                  username: username.trim(),
                  ...(password ? { password } : {}),
                },
              });
            } else {
              create.mutate({ username: username.trim(), password });
            }
          }}
        >
          <div className="space-y-2">
            <Label htmlFor={usernameId}>{t("adminUsers.username")}</Label>
            <Input
              id={usernameId}
              autoComplete="off"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              disabled={pending}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor={passwordId}>
              {t(user ? "adminUsers.newPassword" : "adminUsers.password")}
            </Label>
            <Input
              id={passwordId}
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required={!user}
              disabled={pending}
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={pending}
              onClick={onClose}
            >
              {t("adminUsers.cancel")}
            </Button>
            <Button
              type="submit"
              disabled={!canSave || pending}
              loading={pending}
            >
              {t("adminUsers.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
