import { useState } from "react";
import IconComponent from "../../components/genericIconComponent";

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

  const dragOver = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((types) => types === "Files") && onFileDrop) {
      setIsDragging(true);
    }
  };

  const dragEnter = (e) => {
    if (e.dataTransfer.types.some((types) => types === "Files") && onFileDrop) {
      setIsDragging(true);
    }
    e.preventDefault();
  };

  const dragLeave = (e) => {
    e.preventDefault();
    if (onFileDrop) setIsDragging(false);
  };

  const onDrop = (e) => {
    e.preventDefault();
    if (onFileDrop) onFileDrop(e);
    setIsDragging(false);
  };

  return (
    <div
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
      className={
        "h-full w-full " +
        (isDragging
          ? "mb-24 flex flex-col items-center justify-center gap-4 text-2xl font-light"
          : "")
      }
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
