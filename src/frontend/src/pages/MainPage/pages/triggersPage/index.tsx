import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useGetTriggers } from "@/controllers/API/queries/triggers";
import TriggerFormModal from "./components/TriggerFormModal";
import TriggerJobsDrawer from "./components/TriggerJobsDrawer";
import TriggersTable from "./components/TriggersTable";
import type { Trigger } from "./types";

export default function TriggersPage() {
  const { t } = useTranslation();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Trigger | null>(null);
  const [jobsTrigger, setJobsTrigger] = useState<Trigger | null>(null);

  const { data: triggers, isLoading } = useGetTriggers({});

  const handleCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const handleEdit = (trigger: Trigger) => {
    setEditing(trigger);
    setFormOpen(true);
  };

  return (
    <div className="flex h-full w-full" data-testid="triggers-wrapper">
      <div
        className={`flex h-full w-full flex-col overflow-y-auto transition-all duration-200 ${
          jobsTrigger ? "mr-80" : ""
        }`}
      >
        <div className="flex h-full w-full flex-col xl:container">
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
              <Button
                variant="default"
                size="md"
                onClick={handleCreate}
                data-testid="create-trigger-button"
              >
                <ForwardedIconComponent name="Plus" className="h-4 w-4" />
                {t("triggers.create")}
              </Button>
            </div>

            <div className="text-sm text-muted-foreground pb-6">
              {t("triggers.description")}
            </div>

            <TriggersTable
              triggers={triggers ?? []}
              isLoading={isLoading}
              onEdit={handleEdit}
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

      <TriggerFormModal
        open={formOpen}
        setOpen={setFormOpen}
        existingTrigger={editing}
      />
    </div>
  );
}
