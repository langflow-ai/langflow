import { useEffect, useState } from "react";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";

export default function DragWrapComponent({
  onFileDrop,
  children,
}: {
  onFileDrop?: (e: any) => void;
  children: JSX.Element | JSX.Element[];
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const isIOModalOpen = useFlowsManagerStore((state) => state.IOModalOpen);
  const [filesCount, setFilesCount] = useState(0);
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
    setMousePosition({ x: e.clientX, y: e.clientY });
    if (
      e.dataTransfer.types.some((types) => types === "Files") &&
      onFileDrop &&
      !isIOModalOpen
    ) {
      setIsDragging(true);
      setFilesCount(e.dataTransfer.items.length);
    }
  };

  const dragEnter = (e) => {
    if (
      e.dataTransfer.types.some((types) => types === "Files") &&
      onFileDrop &&
      !isIOModalOpen
    ) {
      setIsDragging(true);
      setFilesCount(e.dataTransfer.items.length);
    }
    e.preventDefault();
  };

  const dragLeave = (e) => {
    e.preventDefault();
    if (onFileDrop && !isIOModalOpen) {
      setIsDragging(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    if (onFileDrop && !isIOModalOpen) onFileDrop(e);
    setIsDragging(false);
  };

  const image = `url("data:image/svg+xml,%3Csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg'%3E%3Crect width='100%25' height='100%25' fill='none' rx='16' ry='16' stroke='%23FFFFFF' stroke-width='2px' stroke-dasharray='5%2c 5' stroke-dashoffset='0' stroke-linecap='butt'/%3E%3C/svg%3E")`;

  return (
    <div
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
      className={cn("relative h-full w-full transition-all")}
      data-testid="drag-wrap-component"
    >
      <div
        className={cn(
          "h-full w-full transition-all",
          isDragging ? "opacity-50" : "",
        )}
      >
        {children}
      </div>

      <div
        className={cn(
          "pointer-events-none absolute top-0 h-full w-full rounded-2xl bg-placeholder-foreground transition-all",
          isDragging ? "opacity-100" : "opacity-0",
        )}
        style={{
          WebkitMaskImage: image,
          maskImage: image,
        }}
      />

      {isDragging && (
        <div
          className="pointer-events-none fixed -translate-x-1/2"
          style={{
            left: `${mousePosition.x}px`,
            top: `${mousePosition.y + 55}px`,
          }}
        >
          <div className="w-44 rounded-2xl bg-accent-indigo-foreground px-2.5 py-0.5 text-center backdrop-blur-sm">
            <span className="font-mono text-xs text-primary-foreground">
              Drop file{filesCount > 1 ? "s" : ""} to upload
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
