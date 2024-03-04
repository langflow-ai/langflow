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

  const handleClick = async () => {
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
