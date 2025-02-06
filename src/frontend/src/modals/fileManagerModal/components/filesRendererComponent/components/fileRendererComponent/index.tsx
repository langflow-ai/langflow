import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { FileType } from "@/types/file_management";
import { formatFileSize } from "@/utils/stringManipulation";
import { FILE_ICONS } from "@/utils/styleUtils";
import { cn } from "@/utils/utils";
import { useEffect, useState } from "react";
import FilesContextMenuComponent from "../../../filesContextMenuComponent";

export default function FileRendererComponent({
  file,
  handleFileSelect,
  selectedFiles,
  handleRemove,
  handleRename,
  index,
}: {
  file: FileType;
  handleFileSelect?: (path: string) => void;
  selectedFiles?: string[];
  handleRemove?: (path: string) => void;
  handleRename?: (id: string, name: string) => void;
  index: number;
}) {
  const type = file.path.split(".").pop() ?? "";

  const [openRename, setOpenRename] = useState(false);
  const [newName, setNewName] = useState(file.name);

  const handleOpenRename = () => {
    handleRename && setOpenRename(true);
  };

  useEffect(() => {
    setNewName(file.name);
  }, [openRename]);

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

          {openRename ? (
            <div className="w-full">
              <Input
                value={newName}
                autoFocus
                onChange={(e) => setNewName(e.target.value)}
                onBlur={() => {
                  setOpenRename(false);
                  handleRename?.(file.id, newName);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    setOpenRename(false);
                    handleRename?.(file.id, newName);
                  }
                }}
                onClick={(e) => e.stopPropagation()}
                className="h-6 py-1"
              />
            </div>
          ) : (
            <span
              className="cursor-text text-sm font-medium"
              onDoubleClick={(e) => {
                e.stopPropagation();
                setOpenRename(true);
              }}
            >
              {file.name}
            </span>
          )}
          {!handleRemove && (
            <span className="shrink-0 text-xs text-muted-foreground">
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
        <FilesContextMenuComponent handleRename={handleOpenRename} file={file}>
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
}
