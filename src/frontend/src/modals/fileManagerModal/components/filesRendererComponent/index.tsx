import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { FileType } from "@/types/file_management";
import { formatFileSize } from "@/utils/stringManipulation";
import { FILE_ICONS } from "@/utils/styleUtils";
import { cn } from "@/utils/utils";
import FilesContextMenuComponent from "../filesContextMenuComponent";

export default function FilesRendererComponent({
  files,
  handleFileSelect,
  selectedFiles,
  handleRemove,
}: {
  files: FileType[];
  handleFileSelect?: (name: string) => void;
  selectedFiles?: string[];
  handleRemove?: (name: string) => void;
}) {
  return files.map((file, index) => {
    const type = file.path.split(".").pop() ?? "";
    return (
      <div
        key={index}
        className={cn(
          "flex items-center justify-between rounded-lg py-2",
          handleFileSelect ? "cursor-pointer px-3 hover:bg-accent" : "",
        )}
        onClick={() => handleFileSelect?.(file.path)}
      >
        <div className="flex items-center gap-4">
          {handleFileSelect && (
            <div className="flex" onClick={(e) => e.stopPropagation()}>
              <Checkbox
                checked={selectedFiles?.includes(file.path)}
                onCheckedChange={() => handleFileSelect?.(file.path)}
              />
            </div>
          )}
          <div className="flex items-center gap-2">
            <ForwardedIconComponent
              name={FILE_ICONS[type]?.icon ?? "File"}
              className={cn(
                "h-6 w-6 shrink-0",
                FILE_ICONS[type]?.color ?? undefined,
              )}
            />
            <span className="text-sm font-medium">{file.name}</span>
            {!handleRemove && (
              <span className="text-xs text-muted-foreground">
                {formatFileSize(file.size)}
              </span>
            )}
          </div>
        </div>
        {handleRemove ? (
          <Button
            size="iconMd"
            variant="ghost"
            className="hover:bg-destructive/5"
            onClick={(e) => {
              e.stopPropagation();
              handleRemove?.(file.path);
            }}
          >
            <ForwardedIconComponent
              name="X"
              className="h-5 w-5 shrink-0 text-destructive"
            />
          </Button>
        ) : (
          <FilesContextMenuComponent file={file}>
            <Button
              size="iconMd"
              variant="ghost"
              className="hover:bg-secondary-foreground/5"
              onClick={(e) => {
                e.stopPropagation();
              }}
            >
              <ForwardedIconComponent
                name="EllipsisVertical"
                className="h-5 w-5 shrink-0"
              />
            </Button>
          </FilesContextMenuComponent>
        )}
      </div>
    );
  });
}
