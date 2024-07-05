import IconComponent from "../../components/genericIconComponent";
import { NodeDataType } from "../../types/flow";
import { cn } from "../../utils/utils";
import { Button } from "./button";

function RefreshButton({
  isLoading,
  disabled,
  name,
  button_text,
  data,
  handleUpdateValues,
  className,
  id,
}: {
  isLoading: boolean;
  disabled: boolean;
  name: string;
  button_text?: string;
  data: NodeDataType;
  className?: string;
  handleUpdateValues: (name: string, data: NodeDataType) => void;
  id: string;
}) {
  const handleClick = async () => {
    if (disabled) return;
    handleUpdateValues(name, data);
  };

  const classNames = cn(className, disabled ? "cursor-not-allowed" : "");

  // icon class name should take into account the disabled state and the loading state
  const disabledIconTextClass = disabled ? "text-muted-foreground" : "";
  const iconClassName = cn("h-4 w-4 animate-wiggle", disabledIconTextClass);

  return (
    <Button
      variant="primary"
      disabled={disabled}
      className={classNames}
      onClick={handleClick}
      id={id}
      loading={isLoading}
    >
      {button_text && <span className="mr-1">{button_text}</span>}
      <IconComponent
        name={"RefreshCcw"}
        className={iconClassName}
        id={id + "-icon"}
      />
    </Button>
  );
}

export { RefreshButton };
