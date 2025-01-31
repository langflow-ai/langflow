import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ImportButtonComponent from "../importButtonComponent";

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

      <ImportButtonComponent />
    </div>
  );
}
