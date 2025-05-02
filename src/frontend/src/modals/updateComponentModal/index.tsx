import { Checkbox } from "@/components/ui/checkbox";
import useDuplicateFlows from "@/pages/MainPage/hooks/use-handle-duplicate";
import useFlowStore from "@/stores/flowStore";
import { APIClassType } from "@/types/api";
import { cn } from "@/utils/utils";
import { useState } from "react";
import BaseModal from "../baseModal";

export default function UpdateComponentModal({
  open,
  setOpen,
  onUpdateNode,
  children,
  components,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
  onUpdateNode: () => void;
  children?: React.ReactNode;
  components: { node: APIClassType; nodeId: string; isBreaking: boolean }[];
}) {
  const [backupFlow, setBackupFlow] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const currentFlow = useFlowStore((state) => state.currentFlow);

  const { handleDuplicate } = useDuplicateFlows({
    flow: currentFlow
      ? { ...currentFlow, name: currentFlow.name + " (Backup)" }
      : undefined,
  });

  const handleUpdate = () => {
    setLoading(true);
    if (backupFlow) {
      handleDuplicate().then(() => {
        onUpdateNode();
        setLoading(false);
        setOpen(false);
      });
    } else {
      onUpdateNode();
      setLoading(false);
      setOpen(false);
    }
  };
  return (
    <BaseModal
      closeButtonClassName="!top-2 !right-3"
      open={open}
      setOpen={setOpen}
      size="small-update"
      className="px-4 py-3"
    >
      <BaseModal.Trigger asChild>{children ?? <></>}</BaseModal.Trigger>
      <BaseModal.Header>
        <span className="">
          Update{" "}
          {components.length > 1
            ? "components"
            : components[0].node.display_name}
        </span>
      </BaseModal.Header>
      <BaseModal.Content overflowHidden>
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-3 text-sm text-muted-foreground">
            {components.length > 1 ? (
              <p>
                Breaking updates disconnect components and may require
                reconnecting inputs or outputs after updating. Components from
                the sidebar always use the latest version.
              </p>
            ) : (
              <>
                <p>
                  This update includes{" "}
                  <span className="font-semibold text-accent-amber-foreground">
                    breaking changes
                  </span>{" "}
                  that may disconnect this component from your flow. You might
                  need to reconnect inputs or outputs after updating.
                </p>
                <p>
                  Components added from the sidebar always use the latest
                  version.
                </p>
              </>
            )}
          </div>
          <div
            className={cn(
              "mb-3 flex items-center gap-3 rounded-md border p-3 text-sm",
              !backupFlow && "border-accent-amber-foreground bg-accent-amber",
            )}
          >
            <Checkbox
              checked={backupFlow}
              onCheckedChange={(checked) =>
                setBackupFlow(checked === "indeterminate" ? false : checked)
              }
              className="bg-muted"
              id="backupFlow"
            />
            <label htmlFor="backupFlow">
              Save a backup flow in case something breaks
            </label>
          </div>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: "Update Component",
          onClick: handleUpdate,
          loading,
        }}
      ></BaseModal.Footer>
    </BaseModal>
  );
}
