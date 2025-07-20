import IconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

export const FolderSelectItem = ({ name, iconName }) => (
  <div
    className={cn(
      name === "Delete" ? "text-destructive" : "",
      "flex items-center font-medium",
    )}
  >
    <IconComponent name={iconName} className="mr-2 w-4" />
    <span>{name}</span>
  </div>
);
