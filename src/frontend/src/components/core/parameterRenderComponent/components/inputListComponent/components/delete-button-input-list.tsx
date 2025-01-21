import IconComponent from "@/components/common/genericIconComponent";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cn } from "@/utils/utils";
import { getTestId } from "../helpers/get-test-id";

export const DeleteButtonInputList = ({
  index,
  removeInput,
  disabled,
  editNode,
  componentName,
}: {
  index: number;
  removeInput: (e: React.MouseEvent) => void;
  disabled: boolean;
  editNode: boolean;
  componentName: string;
}) => {
  return (
    <button
      disabled={disabled}
      onClick={removeInput}
      data-testid={getTestId("delete", index, editNode, componentName)}
      className={cn(
        "hit-area-icon delete-btn-group flex items-center justify-center",
        disabled
          ? "pointer-events-none bg-background hover:bg-background"
          : "bg-background hover:bg-smooth-red hover:text-destructive",
        editNode && "h-4 w-4",
      )}
    >
      <IconComponent
        name="X"
        className={cn(
          "icon-size justify-self-center text-muted-foreground",
          !disabled &&
            "hover:cursor-pointer [.delete-btn-group:hover_&]:text-destructive",
        )}
        strokeWidth={ICON_STROKE_WIDTH}
      />
    </button>
  );
};

export default DeleteButtonInputList;
