import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { usePostUploadFileV2 } from "@/controllers/API/queries/file-management";
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

  const { mutate: uploadFile } = usePostUploadFileV2();

  useEffect(() => {
    setNewName(file.name);
  }, [openRename]);

  return (
    <div
      key={index}
      className={cn(
        "flex w-full items-center justify-between gap-2 overflow-hidden rounded-lg py-2",
        handleFileSelect ? "cursor-pointer px-3 hover:bg-accent" : "",
      )}
      onClick={() => {
        if (!file.progress) handleFileSelect?.(file.path);
      }}
    >
      <div className="flex w-full items-center gap-4 overflow-hidden">
        {handleFileSelect && (
          <div
            className={cn(
              "flex shrink-0",
              file.progress !== undefined &&
                "pointer-events-none cursor-not-allowed",
            )}
            onClick={(e) => e.stopPropagation()}
          >
            <Checkbox
              data-testid={`checkbox-${file.name}`}
              checked={selectedFiles?.includes(file.path)}
              onCheckedChange={() => handleFileSelect?.(file.path)}
            />
          </div>
        )}
        <div className="flex w-full items-center gap-2 overflow-hidden">
          {file.progress !== undefined && file.progress !== -1 ? (
            <div className="flex h-6 items-center justify-center text-xs font-semibold text-muted-foreground">
              {Math.round(file.progress * 100)}%
            </div>
          ) : (
            <ForwardedIconComponent
              name={FILE_ICONS[type]?.icon ?? "File"}
              className={cn(
                "h-6 w-6 shrink-0",
                file.progress !== undefined
                  ? "text-placeholder-foreground"
                  : (FILE_ICONS[type]?.color ?? undefined),
              )}
            />
          )}

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
                data-testid={`rename-input-${file.name}`}
              />
            </div>
          ) : (
            <span
              className={cn(
                "flex flex-1 items-center gap-2 overflow-hidden text-sm font-medium",
                file.progress !== undefined &&
                  file.progress === -1 &&
                  "pointer-events-none text-placeholder-foreground",
              )}
              onDoubleClick={(e) => {
                e.stopPropagation();
                if (!file.progress && !handleRemove) {
                  setOpenRename(true);
                }
              }}
            >
              <ShadTooltip content={`${file.name}.${type}`} side="bottom">
                <span
                  className={cn(
                    "w-full cursor-text overflow-hidden truncate",
                    handleRemove && "cursor-default",
                  )}
                >
                  {file.name}.{type}
                </span>
              </ShadTooltip>
              <span className="shrink-0 cursor-default text-xs font-normal text-muted-foreground">
                {formatFileSize(file.size)}
              </span>
            </span>
          )}
          {file.progress !== undefined && file.progress === -1 ? (
            <span className="text-[13px] text-primary">
              Upload failed,{" "}
              <span
                className="cursor-pointer text-accent-pink-foreground underline"
                onClick={(e) => {
                  e.stopPropagation();
                  if (file.file) {
                    uploadFile({ file: file.file });
                  }
                }}
              >
                try again?
              </span>
            </span>
          ) : (
            <></>
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {handleRemove ? (
          <Button
            size="iconMd"
            variant="ghost"
            className="hover:bg-accent"
            data-testid={`remove-file-button-${file.name}`}
            onClick={(e) => {
              e.stopPropagation();
              handleRemove?.(file.path);
            }}
          >
            <ForwardedIconComponent
              name="X"
              className="h-5 w-5 shrink-0 text-muted-foreground"
            />
          </Button>
        ) : file.progress === undefined ? (
          <FilesContextMenuComponent
            handleRename={handleOpenRename}
            file={file}
            simplified
          >
            <Button
              size="iconMd"
              data-testid={`context-menu-button-${file.name}`}
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
        ) : (
          <></>
        )}
      </div>
    </div>
  );
}
