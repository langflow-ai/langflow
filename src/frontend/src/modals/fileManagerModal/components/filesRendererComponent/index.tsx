import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { FileType } from "@/types/file_management";
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
    const type = file.name.split(".").pop() ?? "";
    return (
      <div
        className={cn(
          "flex items-center justify-between rounded-lg py-2",
          handleFileSelect ? "cursor-pointer px-3 hover:bg-accent" : "",
        )}
        onClick={() => handleFileSelect?.(file.id)}
      >
        <div className="flex items-center gap-4">
          {handleFileSelect && (
            <div className="flex" onClick={(e) => e.stopPropagation()}>
              <Checkbox
                checked={selectedFiles?.includes(file.id)}
                onCheckedChange={() => handleFileSelect?.(file.id)}
              />
            </div>
          )}
          <div className="flex items-center gap-2">
            <ForwardedIconComponent
              name={FILE_ICONS[type].icon}
              className={cn("h-6 w-6 shrink-0", FILE_ICONS[type].color)}
            />
            <span className="text-sm font-medium">{file.name}</span>
            <span className="text-xs text-muted-foreground">{file.size}</span>
          </div>
        </div>
        {handleRemove ? (
          <Button
            size="iconMd"
            variant="ghost"
            className="hover:bg-destructive/5"
            onClick={(e) => {
              e.stopPropagation();
              handleRemove?.(file.id);
            }}
          >
            <ForwardedIconComponent
              name="X"
              className="h-5 w-5 shrink-0 text-destructive"
            />
          </Button>
        ) : (
          <FilesContextMenuComponent
            isLocal={index % 2 === 0}
            handleSelectOptionsChange={() => {}}
          >
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
