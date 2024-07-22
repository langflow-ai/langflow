const useDragAndDrop = (setIsDragging: (value: boolean) => void) => {
  const dragOver = (e) => {
    e.preventDefault();
    if (e.dataTransfer.types.some((type) => type === "Files")) {
      setIsDragging(true);
    }
  };

  const dragEnter = (e) => {
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
