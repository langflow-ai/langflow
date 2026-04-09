import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { formatFileSize } from "../utils";

interface FilesPanelProps {
  files: File[];
  onRemoveFile: (index: number) => void;
}

export function FilesPanel({ files, onRemoveFile }: FilesPanelProps) {
  return (
    <div className="flex h-full flex-col">
      {/* Sticky header */}
      <div className="flex items-center gap-2 text-base font-semibold p-3 pb-1">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted">
          <ForwardedIconComponent name="FileStack" className="h-4 w-4" />
        </div>
        Sources
        {files.length > 0 && (
          <span className="text-xs font-normal text-muted-foreground">
            ({files.length} {files.length === 1 ? "file" : "files"},{" "}
            {formatFileSize(files)})
          </span>
        )}
      </div>
      {/* Scrollable file list */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        <div className="flex flex-col gap-1">
          {files.map((file, index) => (
            <div
              key={`${file.name}-${index}`}
              className="group flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-muted"
            >
              <div className="flex items-center gap-2 truncate">
                <ForwardedIconComponent
                  name="FileText"
                  className="h-4 w-4 shrink-0 text-muted-foreground"
                />
                <span className="truncate text-sm">{file.name}</span>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                onClick={() => onRemoveFile(index)}
              >
                <ForwardedIconComponent name="X" className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
