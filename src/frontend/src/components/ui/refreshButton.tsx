import IconComponent from "../../components/genericIconComponent";
import { cn } from "../../utils/utils";
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
    "group text-placeholder p-1 h-6 w-6",
  );

  // icon class name should take into account the disabled state and the loading state
  const disabledIconTextClass = disabled ? "text-muted-foreground" : "";
  const iconClassName = cn(
    "h-4 w-4 animate-wiggle group-hover:text-primary text-placeholder",
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
        strokeWidth={2}
      />
    </Button>
  );
}

export { RefreshButton };
