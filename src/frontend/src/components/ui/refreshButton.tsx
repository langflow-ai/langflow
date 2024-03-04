import { useState } from "react";
import IconComponent from "../../components/genericIconComponent";
import { NodeDataType } from "../../types/flow";
import { cn } from "../../utils/utils";
function RefreshButton({
  name,
  data,
  handleUpdateValues,
}: {
  name: string;
  data: NodeDataType;
  handleUpdateValues: (name: string, data: NodeDataType) => void;
}) {
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = () => {
    setIsLoading(true);
    console.log("refreshing");
    handleUpdateValues(name, data);
    setInterval(() => {
      setIsLoading(false);
    }, 500);
  };

  return (
    <button
      className="extra-side-bar-buttons ml-2 mt-1 w-1/6"
      onClick={handleClick}
    >
      <IconComponent
        name={isLoading ? "Loader2" : "RefreshCcw"}
        className={cn("h-4 w-4", isLoading ? "animate-spin" : "animate-wiggle")}
      />
    </button>
  );
}

export { RefreshButton };
