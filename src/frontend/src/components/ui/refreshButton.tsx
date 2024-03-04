import IconComponent from "../../components/genericIconComponent";
import { NodeDataType } from "../../types/flow";
import { cn } from "../../utils/utils";

function RefreshButton({
  isLoading,
  disabled,
  name,
  data,
  handleUpdateValues,
  className,
  id,
}: {
  isLoading: boolean;
  disabled: boolean;
  name: string;
  data: NodeDataType;
  className?: string;
  handleUpdateValues: (name: string, data: NodeDataType) => void;
  id: string;
}) {
  const handleClick = async () => {
    if (disabled) return;
    handleUpdateValues(name, data);
  };

  const classNames = cn(
    className,
    disabled ? "cursor-not-allowed" : "cursor-pointer"
  );

  // icon class name should take into account the disabled state and the loading state
  const disabledIconTextClass = disabled ? "text-muted-foreground" : "";
  const iconClassName = cn(
    "h-4 w-4",
    isLoading ? "animate-spin" : "animate-wiggle",
    disabledIconTextClass
  );

  return (
    <button className={classNames} onClick={handleClick} id={id}>
      <IconComponent
        name={isLoading ? "Loader2" : "RefreshCcw"}
        className={iconClassName}
        id={id + "-icon"}
      />
    </button>
  );
}

export { RefreshButton };
