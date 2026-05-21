import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  useDeleteAllTriggers,
  useDeleteTrigger,
  useGetTriggers,
} from "@/controllers/API/queries/triggers";
import useAlertStore from "@/stores/alertStore";
import BulkDeleteConfirmDialog from "./components/BulkDeleteConfirmDialog";
import TriggerCreateModal from "./components/TriggerCreateModal";
import TriggerJobsDrawer from "./components/TriggerJobsDrawer";
import TriggersTable, { triggerKey } from "./components/TriggersTable";
import type { TriggerInstance } from "./types";

/**
 * Read-mostly trigger management page.
 *
 * Triggers are created by dropping a CronTrigger component into a
 * flow; this page only aggregates the resulting set across the
 * user's flows and offers two actions:
 *
 *   - per-row "Open in editor" / "View jobs" / "Delete"
 *   - bulk delete (selected rows or all)
 *
 * Deleting any trigger here strips its node from the owning flow's
 * data via the backend; the flow-save lifecycle hook then cancels
 * the trigger's queued jobs. No state lives outside the canvas.
 */
export default function TriggersPage() {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((s) => s.setErrorData);
  const setSuccessData = useAlertStore((s) => s.setSuccessData);

  const { data: triggers, isLoading } = useGetTriggers();
  const allTriggers = useMemo(() => triggers ?? [], [triggers]);

  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [jobsTrigger, setJobsTrigger] = useState<TriggerInstance | null>(null);
  const [bulkDialogOpen, setBulkDialogOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  const { mutate: deleteOne, isPending: isDeletingOne } = useDeleteTrigger({
    onError: (err) =>
      setErrorData({
        title: t("triggers.deleteError"),
        list: [String((err as Error)?.message ?? err)],
      }),
  });

  const { mutate: deleteAll, isPending: isDeletingAll } = useDeleteAllTriggers({
    onSuccess: (data) => {
      const summary = data;
      setSuccessData({
        title: t("triggers.bulkDeleteSuccess", {
          flows: summary.flows_updated,
          components: summary.components_removed,
        }),
      });
      setSelectedKeys(new Set());
      setBulkDialogOpen(false);
    },
    onError: (err) =>
      setErrorData({
        title: t("triggers.bulkDeleteError"),
        list: [String((err as Error)?.message ?? err)],
      }),
  });

  const handleSelectToggle = (key: string) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleSelectAll = (allKeys: string[], shouldSelectAll: boolean) => {
    setSelectedKeys(shouldSelectAll ? new Set(allKeys) : new Set());
  };

  /**
   * Two pathways converge here:
   *
   * - "Delete selected": fire ``deleteOne`` for each selected row.
   *   We use the single endpoint serially rather than the bulk one
   *   because the bulk endpoint strips every CronTrigger on the
   *   server side (no per-row selection there).
   * - "Delete all": call the bulk endpoint exactly once.
   */
  const handleBulkConfirm = () => {
    if (selectedKeys.size === 0 || selectedKeys.size === allTriggers.length) {
      deleteAll();
      return;
    }
    const targets = allTriggers.filter((t) => selectedKeys.has(triggerKey(t)));
    targets.forEach((trigger) =>
      deleteOne({
        flow_id: trigger.flow_id,
        component_id: trigger.component_id,
      }),
    );
    setSuccessData({
      title: t("triggers.bulkDeleteSuccess", {
        flows: new Set(targets.map((tg) => tg.flow_id)).size,
        components: targets.length,
      }),
    });
    setSelectedKeys(new Set());
    setBulkDialogOpen(false);
  };

  const selectedCount = selectedKeys.size;
  const bulkLabel =
    selectedCount > 0
      ? t("triggers.deleteSelected", { count: selectedCount })
      : t("triggers.deleteAll");
  const bulkCount =
    selectedCount > 0 ? selectedCount : allTriggers.length;
  const showBulkAction = allTriggers.length > 0;

  return (
    <div className="flex h-full w-full" data-testid="triggers-wrapper">
      <div
        className={`flex h-full w-full flex-col overflow-y-auto transition-all duration-200 ${
          jobsTrigger ? "mr-96" : ""
        }`}
      >
        {/*
          When the jobs drawer is open it already eats 384px on the
          right via mr-96; the inner xl:container would also cap the
          remaining width to ~1280px and leave a visible empty gap
          between the page content's right edge and the drawer. Drop
          the container constraint while the drawer is open so the
          content fills the freed space.
        */}
        <div
          className={`flex h-full w-full flex-col ${
            jobsTrigger ? "" : "xl:container"
          }`}
        >
          <div className="flex flex-1 flex-col justify-start px-5 pt-10">
            <div
              className="flex items-center justify-between pb-4"
              data-testid="mainpage_title"
            >
              <div className="flex items-center text-xl font-semibold">
                <div className="h-7 w-10 transition-all group-data-[open=true]/sidebar-wrapper:md:w-0 lg:hidden">
                  <div className="relative left-0 opacity-100 transition-all group-data-[open=true]/sidebar-wrapper:md:opacity-0">
                    <SidebarTrigger>
                      <ForwardedIconComponent
                        name="PanelLeftOpen"
                        className="h-4 w-4"
                      />
                    </SidebarTrigger>
                  </div>
                </div>
                {t("triggers.title")}
              </div>
              <div className="flex items-center gap-2">
                {showBulkAction && (
                  <Button
                    variant="outline"
                    size="md"
                    data-testid="triggers-bulk-delete-button"
                    onClick={() => setBulkDialogOpen(true)}
                    disabled={isDeletingOne || isDeletingAll}
                  >
                    <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
                    {bulkLabel}
                  </Button>
                )}
                <Button
                  variant="default"
                  size="md"
                  data-testid="triggers-new-trigger-button"
                  onClick={() => setCreateOpen(true)}
                >
                  <ForwardedIconComponent name="Plus" className="h-4 w-4" />
                  {t("triggers.create")}
                </Button>
              </div>
            </div>

            <div className="text-sm text-muted-foreground pb-6">
              {t("triggers.description")}
            </div>

            <TriggersTable
              triggers={allTriggers}
              isLoading={isLoading}
              selected={selectedKeys}
              onSelectToggle={handleSelectToggle}
              onSelectAll={handleSelectAll}
              onViewJobs={setJobsTrigger}
            />
          </div>
        </div>
      </div>

      {jobsTrigger && (
        <TriggerJobsDrawer
          trigger={jobsTrigger}
          onClose={() => setJobsTrigger(null)}
        />
      )}

      <BulkDeleteConfirmDialog
        open={bulkDialogOpen}
        setOpen={setBulkDialogOpen}
        count={bulkCount}
        isLoading={isDeletingOne || isDeletingAll}
        onConfirm={handleBulkConfirm}
      />

      <TriggerCreateModal open={createOpen} setOpen={setCreateOpen} />
    </div>
  );
}
