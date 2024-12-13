import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cn } from "@/utils/utils";
import { getButtonClassName } from "../helpers/get-class-name";
import { getTestId } from "../helpers/get-test-id";

export const ButtonInputList = ({
  index,
  value,
  addNewInput,
  removeInput,
  disabled,
  editNode,
  addIcon,
  componentName,
}: {
  index: number;
  value: string[];
  addNewInput: (e) => void;
  removeInput: (index: number, e: React.MouseEvent<HTMLDivElement>) => void;
  disabled: boolean;
  editNode: boolean;
  addIcon: boolean;
  componentName: string;
}) => {
  return (
    <>
      <div
        onClick={
          (index === 0 && value.length <= 1) || addIcon
            ? addNewInput
            : (e) => removeInput(index, e)
        }
        className={cn(
          "hit-area-icon group flex items-center justify-center text-center",
          disabled
            ? "pointer-events-none bg-background hover:bg-background"
            : "",
          (index === 0 && value.length <= 1) || addIcon
            ? "bg-background hover:bg-muted"
            : "hover:bg-smooth-red",
        )}
      >
        <Button
          unstyled
          size="icon"
          className={cn(
            "hit-area-icon flex items-center justify-center",
            getButtonClassName(disabled),
          )}
          data-testid={getTestId(
            (index === 0 && value.length <= 1) || addIcon ? "plus" : "minus",
            index,
            editNode,
            componentName,
          )}
          disabled={disabled}
        >
          <IconComponent
            name={
              (index === 0 && value.length <= 1) || addIcon ? "Plus" : "Trash2"
            }
            className={cn(
              "icon-size justify-self-center text-muted-foreground",
              !disabled && "hover:cursor-pointer hover:text-foreground",
              (index === 0 && value.length <= 1) || addIcon
                ? "group-hover:text-foreground"
                : "group-hover:text-destructive",
            )}
            strokeWidth={ICON_STROKE_WIDTH}
          />
        </Button>
      </div>
    </>
  );
};
