import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cn } from "@/utils/utils";
import { getButtonClassName } from "../helpers/get-class-name";
import { getTestId } from "../helpers/get-test-id";
export const DeleteButtonInputList = ({
  index,
  removeInput,
  disabled,
  editNode,
  componentName,
}: {
  index: number;
  removeInput: (e) => void;
  disabled: boolean;
  editNode: boolean;
  componentName: string;
}) => {
  return (
    <>
      <button
        disabled={disabled}
        onClick={removeInput}
        data-testid={getTestId("delete", index, editNode, componentName)}
        className={cn(
          "hit-area-icon delete-btn-group absolute flex translate-x-[15.35rem] items-center justify-center",
          disabled
            ? "pointer-events-none bg-background hover:bg-background"
            : "bg-background hover:bg-smooth-red",
          editNode && "h-5 w-5 translate-x-[14.2rem]",
        )}
      >
        <IconComponent
          name="X"
          className={cn(
            "icon-size justify-self-center text-muted-foreground",
            !disabled &&
              "hover:cursor-pointer hover:text-destructive [.delete-btn-group:hover_&]:text-destructive",
          )}
          strokeWidth={ICON_STROKE_WIDTH}
        />
      </button>
    </>
  );
};
