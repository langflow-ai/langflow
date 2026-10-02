import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { StorageUpgrade } from "@/controllers/API/queries/knowledge-base-storage/use-get-storage-status";
import { useGetStorageStatus } from "@/controllers/API/queries/knowledge-base-storage/use-get-storage-status";
import { usePostStorageRetry } from "@/controllers/API/queries/knowledge-base-storage/use-post-storage-retry";
import useAuthStore from "@/stores/authStore";

const PHASE_KEYS: Record<string, string> = {
  discovered: "storageUpgrade.queued",
  snapshotting: "storageUpgrade.backingUp",
  exporting: "storageUpgrade.reading",
  importing: "storageUpgrade.copying",
  verified: "storageUpgrade.verifying",
  activated: "storageUpgrade.verifying",
  complete: "storageUpgrade.complete",
  needs_attention: "storageUpgrade.needsAttention",
};

const GUIDANCE_KEYS: Record<string, string> = {
  automatic_upgrade_disabled: "storageUpgrade.disabled",
  single_host_required: "storageUpgrade.singleHost",
  legacy_workers_running: "storageUpgrade.stopOtherInstances",
  local_filesystem_required: "storageUpgrade.localFilesystem",
  remote_source_requires_migration: "storageUpgrade.remote",
  validation_failed: "storageUpgrade.validationFailed",
  interrupted: "storageUpgrade.interrupted",
  automatic_reader_limit: "storageUpgrade.readerLimit",
};

function UpgradeCard({
  store,
  isAdmin,
}: {
  store: StorageUpgrade;
  isAdmin: boolean;
}) {
  const { t } = useTranslation();
  const retry = usePostStorageRetry();
  const [failed, setFailed] = useState(false);
  const isUpgrading = store.storage_state === "migrating";
  return (
    <section
      className="space-y-2 rounded-md border border-border p-3"
      data-testid="storage-upgrade-card"
    >
      <h4 className="text-sm font-medium">{store.name}</h4>
      <p className="text-sm" role="status">
        {t(PHASE_KEYS[store.phase] ?? "storageUpgrade.needsAttention")}
      </p>
      <p className="text-xs text-muted-foreground">
        {t(
          isUpgrading
            ? "storageUpgrade.automatic"
            : !isAdmin
              ? "storageUpgrade.contactAdmin"
              : (GUIDANCE_KEYS[store.error_code ?? ""] ??
                "storageUpgrade.checkStorage"),
        )}
      </p>
      {store.can_retry && store.migration_id && (
        <Button
          size="sm"
          variant="outline"
          disabled={retry.isPending}
          data-testid="storage-upgrade-retry"
          onClick={() => {
            setFailed(false);
            if (!store.migration_id) return;
            retry.mutate(
              { migrationId: store.migration_id },
              { onError: () => setFailed(true) },
            );
          }}
        >
          {t("storageUpgrade.retry")}
        </Button>
      )}
      {failed && (
        <p role="alert" className="text-xs text-destructive">
          {t("storageUpgrade.retryFailed")}
        </p>
      )}
    </section>
  );
}

export function StorageUpgradePanel({
  kbId,
  fallback = null,
}: {
  kbId: string;
  fallback?: ReactNode;
}) {
  const { data } = useGetStorageStatus();
  const store = data?.stores.find((item) => item.kb_id === kbId);
  return store ? (
    <UpgradeCard store={store} isAdmin={data?.is_admin ?? false} />
  ) : (
    fallback
  );
}

export function StorageUpgradeNotice() {
  const { t } = useTranslation();
  const { data } = useGetStorageStatus();
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const userId = useAuthStore((state) => state.userData?.id);
  const queryClient = useQueryClient();
  const previous = useRef<string | null>(null);
  const signature = JSON.stringify({
    viewer: userId,
    stores: data?.stores.map((store) => [
      store.kb_id,
      store.storage_state,
      store.error_code,
    ]),
    revision: data?.revision,
    running: data?.running,
    inventoryComplete: data?.inventory?.complete,
    inventoryIssues: data?.inventory?.issues,
  });
  const visible =
    !!data &&
    (data.running || !!data.stores.length || !!data.inventory?.issues);
  useEffect(() => {
    if (!visible || dismissed === signature) setOpen(false);
  }, [visible, dismissed, signature]);
  useEffect(() => {
    if (!data) return;
    if (previous.current !== null && previous.current !== signature) {
      for (const name of [
        "useGetKnowledgeBases",
        "useGetMemoriesInfinite",
        "useGetMemory",
      ]) {
        queryClient.invalidateQueries({ queryKey: [name] });
      }
    }
    previous.current = signature;
  }, [data, signature, queryClient]);
  if (!data || !visible || dismissed === signature) return null;
  const needsAttention =
    data.stores.some((store) => store.storage_state !== "migrating") ||
    !!data.inventory?.issues;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <div
        className="fixed bottom-4 right-4 z-50 max-w-sm rounded-lg border border-border bg-background p-3 shadow-lg"
        data-testid="storage-upgrade-notice"
        role="region"
        aria-label={t("storageUpgrade.title")}
      >
        <p role="status" className="mb-2 text-sm">
          {t(
            needsAttention
              ? "storageUpgrade.needsAttention"
              : "storageUpgrade.title",
          )}
        </p>
        <DialogTrigger asChild>
          <Button size="sm" variant="outline">
            {t("storageUpgrade.viewProgress")}
          </Button>
        </DialogTrigger>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setDismissed(signature)}
        >
          {t("common.close")}
        </Button>
      </div>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("storageUpgrade.title")}</DialogTitle>
          <DialogDescription>{t("storageUpgrade.preserved")}</DialogDescription>
        </DialogHeader>
        <div className="max-h-96 space-y-3 overflow-y-auto">
          {data.running && !data.stores.length && (
            <p role="status" className="text-sm">
              {t("storageUpgrade.queued")}
            </p>
          )}
          {data.stores.map((store) => (
            <UpgradeCard
              key={store.kb_id}
              store={store}
              isAdmin={data.is_admin}
            />
          ))}
          {!!data.inventory?.issues && (
            <p role="alert" className="text-sm">
              {t("storageUpgrade.inventory")}
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
