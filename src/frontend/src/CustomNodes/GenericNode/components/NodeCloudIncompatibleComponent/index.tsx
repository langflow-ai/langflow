import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

export default function NodeCloudIncompatibleComponent() {
  return (
    <div
      className={cn(
        "flex w-full items-center gap-3 border-b bg-muted p-2 px-4 py-2",
      )}
      data-testid="cloud-incompatible-banner"
    >
      <ForwardedIconComponent
        name="CloudOff"
        className="h-3.5 w-3.5 shrink-0 text-accent-emerald-foreground"
      />
      <div className="mb-px flex-1 truncate text-mmd font-medium">
        Not available in cloud
      </div>
    </div>
  );
}
