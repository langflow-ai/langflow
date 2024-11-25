import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cn } from "../../utils/utils";
import IconComponent from "../common/genericIconComponent";
import { Button } from "./button";

function RefreshButton({
  isLoading,
  disabled,
  button_text,
  handleUpdateValues,
  className,
  editNode,
  id,
}: {
  isLoading: boolean;
  disabled: boolean;
  button_text?: string;
  editNode?: boolean;
  className?: string;
  handleUpdateValues: () => void;
  id: string;
}) {
  const handleClick = async () => {
    if (disabled) return;
    handleUpdateValues();
  };

  const classNames = cn(
    className,
    disabled ? "cursor-not-allowed" : "",
    !editNode ? "py-2.5 px-3" : "px-2 py-1",
    "hit-area-icon group text-muted-foreground p-1",
  );

  // icon class name should take into account the disabled state and the loading state
  const disabledIconTextClass = disabled ? "text-muted-foreground" : "";
  const iconClassName = cn(
    "icon-size animate-wiggle group-hover:text-foreground text-muted-foreground",
    disabledIconTextClass,
  );

  return (
    <Button
      variant="ghost"
      disabled={disabled}
      className={classNames}
      onClick={handleClick}
      id={id}
      size={"icon"}
      loading={isLoading}
    >
      {button_text && <span className="mr-1">{button_text}</span>}
      <IconComponent
        name={"RefreshCcw"}
        className={iconClassName}
        id={id + "-icon"}
        strokeWidth={ICON_STROKE_WIDTH}
      />
    </Button>
  );
}

export { RefreshButton };
