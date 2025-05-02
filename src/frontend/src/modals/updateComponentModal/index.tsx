import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Checkbox } from "@/components/ui/checkbox";
import useDuplicateFlows from "@/pages/MainPage/hooks/use-handle-duplicate";
import useFlowStore from "@/stores/flowStore";
import { APIClassType } from "@/types/api";
import { ComponentsToUpdateType } from "@/types/zustand/flow";
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
  onUpdateNode: (updatedComponents?: string[]) => void;
  children?: React.ReactNode;
  components: ComponentsToUpdateType[];
}) {
  const [backupFlow, setBackupFlow] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedComponents, setSelectedComponents] = useState<Set<string>>(
    new Set(components.map((c) => c.id)),
  );
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
        onUpdateNode(
          components.length > 0 ? Array.from(selectedComponents) : undefined,
        );
        setLoading(false);
        setOpen(false);
      });
    } else {
      onUpdateNode(
        components.length > 0 ? Array.from(selectedComponents) : undefined,
      );
      setLoading(false);
      setOpen(false);
    }
  };

  const toggleComponent = (componentId: string) => {
    const newSelected = new Set(selectedComponents);
    if (newSelected.has(componentId)) {
      newSelected.delete(componentId);
    } else {
      newSelected.add(componentId);
    }
    setSelectedComponents(newSelected);
  };

  const toggleAllComponents = () => {
    if (selectedComponents.size === components.length) {
      setSelectedComponents(new Set());
    } else {
      setSelectedComponents(new Set(components.map((c) => c.id)));
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
            : (components?.[0]?.display_name ?? "")}
        </span>
      </BaseModal.Header>
      <BaseModal.Content overflowHidden>
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-3 text-sm text-muted-foreground">
            {components.length > 1 ? (
              <p>
                <span className="font-semibold text-accent-amber-foreground">
                  Breaking
                </span>{" "}
                updates disconnect components and may require reconnecting
                inputs or outputs after updating. Components from the sidebar
                always use the latest version.
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
          {components.length > 1 && (
            <table className="w-full border-separate border-spacing-y-1 text-sm">
              <thead>
                <tr>
                  <th className="text-left font-medium text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <Checkbox
                        checked={selectedComponents.size === components.length}
                        onCheckedChange={toggleAllComponents}
                        className="bg-muted"
                      />
                      Component
                    </div>
                  </th>
                  <th className="text-left font-medium text-muted-foreground">
                    Update Type
                  </th>
                </tr>
              </thead>
              <tbody>
                {components.map((component) => (
                  <tr key={component.id}>
                    <td className="flex items-center gap-2 py-1 pr-4">
                      <Checkbox
                        checked={selectedComponents.has(component.id)}
                        onCheckedChange={() => toggleComponent(component.id)}
                        className="bg-muted"
                      />
                      {component.icon && (
                        <ForwardedIconComponent
                          name={component.icon}
                          className="h-4 w-4"
                        />
                      )}
                      {component.display_name}
                    </td>
                    <td className="py-1">
                      {component.breakingChange ? (
                        <span className="font-semibold text-accent-amber-foreground">
                          Breaking
                        </span>
                      ) : (
                        <span>Standard</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
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
          label: "Update Component" + (components.length > 1 ? "s" : ""),
          onClick: handleUpdate,
          disabled: selectedComponents.size === 0,
          loading,
        }}
      ></BaseModal.Footer>
    </BaseModal>
  );
}
