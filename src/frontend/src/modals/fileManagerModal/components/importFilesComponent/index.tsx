import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

export default function ImportFilesComponent() {
  return (
    <div className="flex w-full items-center justify-between rounded-2xl bg-muted px-4 py-3">
      <div className="flex items-center gap-4">
        <ForwardedIconComponent name="CloudDownload" className="h-8 w-8" />
        <div className="flex flex-col gap-1">
          <span className="text-sm font-semibold text-primary">
            Import from cloud storage
          </span>
          <span className="text-xs text-muted-foreground">
            Access files from your preferred cloud
          </span>
        </div>
      </div>
      <Button size="sm" className="font-semibold">
        Import from...
        <ForwardedIconComponent name="ChevronDown" className="h-4 w-4" />
      </Button>
    </div>
  );
}
