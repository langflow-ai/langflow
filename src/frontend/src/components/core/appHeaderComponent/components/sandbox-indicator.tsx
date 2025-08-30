import { ShieldAlert } from "lucide-react";
import { useState } from "react";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { ENABLE_SANDBOXING_INDICATORS } from "@/customization/feature-flags";
import SandboxInfoModal from "@/modals/SandboxInfoModal";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "@/utils/utils";

export function SandboxIndicator() {
  const [modalOpen, setModalOpen] = useState(false);
  const sandboxEnabled = useUtilityStore((state) => state.sandboxEnabled);
  const lockAllComponents = useUtilityStore((state) => state.lockAllComponents);

  // Only show sandbox indicator when sandbox is enabled but not in lock mode
  if (!sandboxEnabled || lockAllComponents || !ENABLE_SANDBOXING_INDICATORS)
    return null;

  return (
    <>
      <ShadTooltip
        content={
          <div className="max-w-xs">
            <p className="font-semibold">Sandboxing Enabled</p>
            <p className="text-xs mt-1">
              Modified and/or custom components are subject to restrictions and
              will run in an isolated environment.
            </p>
            <p className="text-xs mt-2 text-blue-400">
              Click for more information
            </p>
          </div>
        }
        side="bottom"
      >
        <div
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-blue-50 border border-blue-400 text-blue-500 dark:bg-gray-800 dark:border-blue-400 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-gray-700 transition-colors cursor-pointer",
          )}
          onClick={() => setModalOpen(true)}
        >
          <ShieldAlert className="h-3.5 w-3.5" />
        </div>
      </ShadTooltip>

      <SandboxInfoModal open={modalOpen} setOpen={setModalOpen} />
    </>
  );
}
