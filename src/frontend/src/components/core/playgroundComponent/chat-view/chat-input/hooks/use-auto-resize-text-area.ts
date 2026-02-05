import { useEffect } from "react";

const useAutoResizeTextArea = (
  value: string,
  inputRef: React.RefObject<HTMLTextAreaElement>,
) => {
  useEffect(() => {
    if (inputRef.current && inputRef.current.scrollHeight !== 0) {
      inputRef.current.style.height = "inherit";
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
    }
  }, [value]);

  return inputRef;
};

export default useAutoResizeTextArea;
