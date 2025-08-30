import { Lock } from "lucide-react";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { ENABLE_SANDBOXING_INDICATORS } from "@/customization/feature-flags";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "@/utils/utils";

export function LockedIndicator() {
  const sandboxEnabled = useUtilityStore((state) => state.sandboxEnabled);
  const lockAllComponents = useUtilityStore((state) => state.lockAllComponents);

  if (!sandboxEnabled || !lockAllComponents || !ENABLE_SANDBOXING_INDICATORS)
    return null;

  return (
    <ShadTooltip
      content={
        <div className="max-w-xs">
          <p className="font-semibold">Components Locked</p>
          <p className="text-xs mt-1">
            Custom components and/or code editing is disabled.
          </p>
        </div>
      }
      side="bottom"
    >
      <div
        className={cn(
          "flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium bg-red-50 border border-red-400 text-red-600 dark:bg-gray-800 dark:border-red-400 dark:text-red-400 cursor-default",
        )}
      >
        <Lock className="h-3.5 w-3.5" />
      </div>
    </ShadTooltip>
  );
}
