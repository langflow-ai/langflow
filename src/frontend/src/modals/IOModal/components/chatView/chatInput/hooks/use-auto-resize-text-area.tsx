import { useEffect } from "react";

const useAutoResizeTextArea = (
  value: string,
  inputRef: React.RefObject<HTMLInputElement>,
) => {
  useEffect(() => {
    if (inputRef.current && inputRef.current.scrollHeight! !== 0) {
      inputRef.current.style!.height = "inherit"; // Reset the height
      inputRef.current.style!.height = `${inputRef.current.scrollHeight!}px`; // Set it to the scrollHeight
    }
  }, [value]);

  return inputRef;
};

export default useAutoResizeTextArea;
