import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";

export const AddFolderButton = ({
  onClick,
  disabled,
  loading,
}: {
  onClick: () => void;
  disabled: boolean;
  loading: boolean;
}) => (
  <ShadTooltip content="Create new folder" styleClasses="z-50">
    <Button
      variant="ghost"
      size="icon"
      className="h-7 w-7 border-0 text-zinc-500 hover:bg-zinc-200 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-white"
      onClick={onClick}
      data-testid="add-folder-button"
      disabled={disabled}
      loading={loading}
    >
      <IconComponent name="Plus" className="h-4 w-4" />
    </Button>
  </ShadTooltip>
);
