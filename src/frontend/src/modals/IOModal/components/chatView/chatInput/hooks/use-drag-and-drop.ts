import { ENABLE_IMAGE_ON_PLAYGROUND } from "@/customization/feature-flags";

const useDragAndDrop = (setIsDragging: (value: boolean) => void) => {
  const dragOver = (e) => {
    if (!ENABLE_IMAGE_ON_PLAYGROUND) return;
    e.preventDefault();
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      setIsDragging(true);
    }
  };

  const dragEnter = (e) => {
    if (!ENABLE_IMAGE_ON_PLAYGROUND) return;
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      setIsDragging(true);
    }
    e.preventDefault();
  };

  const dragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  return {
    dragOver,
    dragEnter,
    dragLeave,
  };
};

export default useDragAndDrop;
