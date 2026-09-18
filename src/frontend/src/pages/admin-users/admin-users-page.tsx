import { useState } from "react";
import { useTranslation } from "react-i18next";
import PaginatorComponent from "@/components/common/paginatorComponent";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useDeleteAdminUser,
  useGetAdminUsers,
  useUpdateAdminUser,
} from "@/controllers/API/queries/auth/use-user-administration";
import useAuthStore from "@/stores/authStore";
import type { Users } from "@/types/api";
import { extractApiErrorCode, extractApiErrorMessages } from "@/utils/apiError";
import { UserFormDialog } from "./user-form-dialog";

export default function AdminUsersPage() {
  const { t } = useTranslation();
  const currentUserId = useAuthStore((state) => state.userData?.id);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [editing, setEditing] = useState<Users | "new" | null>(null);
  const [deleting, setDeleting] = useState<Users | null>(null);
  const [error, setError] = useState<string | null>(null);
  const users = useGetAdminUsers({
    skip: (page - 1) * pageSize,
    limit: pageSize,
    search: search || undefined,
  });
  const onError = (requestError: Error) =>
    setError(
      extractApiErrorCode(requestError) ===
        "RESOURCE_OWNERSHIP_REQUIRES_DISPOSITION"
        ? t("adminUsers.ownedResources")
        : extractApiErrorMessages(requestError).join(" "),
    );
  const update = useUpdateAdminUser({ onError });
  const remove = useDeleteAdminUser({
    onError,
    onSuccess: () => {
      setDeleting(null);
      if (users.data?.users.length === 1 && page > 1) setPage(page - 1);
    },
  });
  const busy = update.isPending || remove.isPending;

  return (
    <section className="flex w-full min-w-0 flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">
            {t("adminUsers.usersTitle")}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("adminUsers.description")}
          </p>
        </div>
        <Button onClick={() => setEditing("new")} data-testid="admin-add-user">
          {t("adminUsers.addTitle")}
        </Button>
      </div>
      <div className="flex w-full min-w-0 flex-col gap-4">
        <form
          className="flex items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setSearch(searchInput.trim());
          }}
        >
          <Input
            icon="Search"
            className="min-w-0 max-w-sm flex-1"
            aria-label={t("adminUsers.search")}
            placeholder={t("adminUsers.search")}
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
          <Button type="submit" variant="outline">
            {t("adminUsers.searchButton")}
          </Button>
        </form>
        {error && !deleting && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {users.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{t("adminUsers.loadError")}</AlertDescription>
            <Button variant="outline" onClick={() => void users.refetch()}>
              {t("common.retry")}
            </Button>
          </Alert>
        ) : users.isLoading ? (
          <p role="status">{t("common.loading")}</p>
        ) : (
          <>
            <div className="overflow-x-auto rounded-lg border">
              <Table
                aria-label={t("adminUsers.usersTitle")}
                className="min-w-[520px]"
              >
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("adminUsers.username")}</TableHead>
                    <TableHead>{t("adminUsers.active")}</TableHead>
                    <TableHead>{t("adminUsers.superuser")}</TableHead>
                    <TableHead>{t("adminUsers.actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.data?.users.map((user) => {
                    const isSelf = currentUserId === user.id;
                    return (
                      <TableRow key={user.id}>
                        <TableCell className="font-medium">
                          {user.username}
                        </TableCell>
                        <TableCell>
                          <Checkbox
                            checked={user.is_active}
                            disabled={isSelf || busy || users.isFetching}
                            aria-label={t("adminUsers.activeFor", {
                              username: user.username,
                            })}
                            onCheckedChange={(checked) => {
                              setError(null);
                              update.mutate({
                                id: user.id,
                                fields: { is_active: checked === true },
                              });
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <Checkbox
                            checked={user.is_superuser}
                            disabled={isSelf || busy || users.isFetching}
                            aria-label={t("adminUsers.superuserFor", {
                              username: user.username,
                            })}
                            onCheckedChange={(checked) => {
                              setError(null);
                              update.mutate({
                                id: user.id,
                                fields: { is_superuser: checked === true },
                              });
                            }}
                          />
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={busy}
                              aria-label={t("adminUsers.editFor", {
                                username: user.username,
                              })}
                              onClick={() => setEditing(user)}
                            >
                              {t("adminUsers.edit")}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={isSelf || busy}
                              aria-label={t("adminUsers.deleteFor", {
                                username: user.username,
                              })}
                              onClick={() => {
                                setError(null);
                                setDeleting(user);
                              }}
                            >
                              {t("adminUsers.delete")}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {users.data?.users.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4}>{t("adminUsers.empty")}</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
            <div>
              <PaginatorComponent
                pageIndex={page}
                pageSize={pageSize}
                totalRowsCount={users.data?.total_count ?? 0}
                paginate={(nextPage, nextSize) => {
                  setPage(nextPage);
                  setPageSize(nextSize);
                }}
              />
            </div>
          </>
        )}
        {editing && (
          <UserFormDialog
            key={editing === "new" ? "new" : editing.id}
            user={editing === "new" ? undefined : editing}
            onClose={() => setEditing(null)}
          />
        )}
        {deleting && (
          <Dialog
            open
            onOpenChange={(open) => {
              if (!open && !remove.isPending) setDeleting(null);
            }}
          >
            <DialogContent>
              <DialogHeader>
                <DialogTitle>
                  {t("adminUsers.deleteFor", { username: deleting.username })}
                </DialogTitle>
                <DialogDescription>
                  {t("adminUsers.deleteDescription")}
                </DialogDescription>
              </DialogHeader>
              {error && (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}
              <DialogFooter>
                <Button
                  variant="outline"
                  disabled={remove.isPending}
                  onClick={() => setDeleting(null)}
                >
                  {t("adminUsers.cancel")}
                </Button>
                <Button
                  variant="destructive"
                  disabled={remove.isPending}
                  loading={remove.isPending}
                  onClick={() => {
                    setError(null);
                    remove.mutate(deleting.id);
                  }}
                >
                  {t("adminUsers.delete")}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>
    </section>
  );
}
