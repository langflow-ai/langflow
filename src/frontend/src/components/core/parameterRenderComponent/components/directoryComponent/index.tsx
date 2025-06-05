import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { createDirectoryUpload } from "@/helpers/create-directory-upload";
import { cn } from "@/utils/utils";
import { InputProps } from "../../types";

export default function DirectoryComponent({
  value,
  handleOnNewValue,
  disabled,
  id,
  placeholder,
  editNode = false,
}: InputProps<string>): JSX.Element {
  const handleDirectoryPicker = async () => {
    if (disabled) return;

    try {
      const selectedDirectory = await createDirectoryUpload();
      console.log("selectedDirectory", selectedDirectory);
      if (selectedDirectory) {
        handleOnNewValue({ value: selectedDirectory });
      }
    } catch (error) {
      console.error("Error selecting directory:", error);
    }
  };

  const isDisabled = disabled;

  return (
    <div className="w-full">
      <div className="relative flex w-full">
        <div className="w-full">
          <input
            id={id}
            type="text"
            value={value || ""}
            onChange={(e) => handleOnNewValue({ value: e.target.value })}
            placeholder={
              placeholder ||
              "Enter full directory path (e.g. /Users/username/Documents/project)"
            }
            disabled={isDisabled}
            className={cn(
              "primary-input h-9 w-full cursor-pointer rounded-r-none text-sm focus:border-border focus:outline-none focus:ring-0",
              !value && "text-placeholder-foreground",
              editNode && "h-6",
            )}
            data-testid="directory-input"
          />
        </div>
        <div>
          <Button
            className={cn(
              "h-9 w-9 rounded-l-none",
              value &&
                "bg-accent-emerald-foreground ring-accent-emerald-foreground hover:bg-accent-emerald-foreground",
              isDisabled &&
                "relative top-[1px] h-9 ring-1 ring-border ring-offset-0 hover:ring-border",
              editNode && "h-6",
            )}
            onClick={handleDirectoryPicker}
            disabled={isDisabled}
            size="icon"
            data-testid="button_select_directory"
            type="button"
            title="Browse for directory (will show directory name only - please type full path manually)"
          >
            <IconComponent
              name={value ? "CircleCheckBig" : "Folder"}
              className={cn(
                value && "text-background",
                isDisabled && "text-muted-foreground",
                "h-4 w-4",
              )}
              strokeWidth={2}
            />
          </Button>
        </div>
      </div>
    </div>
  );
}
