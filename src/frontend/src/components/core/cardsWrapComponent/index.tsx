import { useEffect, useState } from "react";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "../../../utils/utils";
import IconComponent from "../../common/genericIconComponent";

export default function CardsWrapComponent({
  onFileDrop,
  children,
  dragMessage,
}: {
  onFileDrop?: (e: any) => void;
  children: JSX.Element | JSX.Element[];
  dragMessage?: string;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const isIOModalOpen = useFlowsManagerStore((state) => state.IOModalOpen);
  useEffect(() => {
    // Function to handle visibility change
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        // Reset hover state or perform any necessary actions when the tab becomes visible again
        setIsDragging(false);
      }
    };

    // Add event listener for visibility change
    document.addEventListener("visibilitychange", handleVisibilityChange);

    // Cleanup event listener on component unmount
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  const dragOver = (e) => {
    e.preventDefault();
    if (
      e.dataTransfer.types.some((types) => types === "Files") &&
      onFileDrop &&
      !isIOModalOpen
    ) {
      setIsDragging(true);
    }
  };

  const dragEnter = (e) => {
    if (
      e.dataTransfer.types.some((types) => types === "Files") &&
      onFileDrop &&
      !isIOModalOpen
    ) {
      setIsDragging(true);
    }
    e.preventDefault();
  };

  const dragLeave = (e) => {
    e.preventDefault();
    if (onFileDrop && !isIOModalOpen) setIsDragging(false);
  };

  const onDrop = (e) => {
    e.preventDefault();
    if (onFileDrop && !isIOModalOpen) onFileDrop(e);
    setIsDragging(false);
  };

  return (
    <div
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
      className={cn(
        "h-full w-full",
        isDragging
          ? "z-10 mb-36 flex flex-col items-center justify-center gap-4 text-2xl font-light"
          : "",
      )}
    >
      {isDragging ? (
        <>
          <IconComponent name="ArrowUpToLine" className="h-12 w-12 stroke-1" />
          {dragMessage ? dragMessage : "Drop your file here"}
        </>
      ) : (
        children
      )}
    </div>
  );
}
