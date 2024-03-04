import { useEffect, useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import { NodeDataType } from "../../types/flow";
import { cn } from "../../utils/utils";

function RefreshButton({
  disabled,
  name,
  data,
  handleUpdateValues,
  className,
  id,
}: {
  disabled: boolean;
  name: string;
  data: NodeDataType;
  className?: string;
  handleUpdateValues: (name: string, data: NodeDataType) => void;
  id: string;
}) {
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    handleUpdateValues(name, data);
  }, []); // Empty dependency array to run only once

  const handleClick = async () => {
    if (disabled) return;
    setIsLoading(true);
    console.log("refreshing");
    handleUpdateValues(name, data);
    try {
      // Wait for at least 500 milliseconds
      await new Promise((resolve) => setTimeout(resolve, 500));
      // Continue with the request
      // If the request takes longer than 500 milliseconds, it will not wait an additional 500 milliseconds
    } catch (error) {
      console.error("Error occurred while waiting for refresh:", error);
    } finally {
      setIsLoading(false);
    }
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
