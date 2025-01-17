import { useEffect } from "react";

const useFocusOnUnlock = (
  lockChat: boolean,
  inputRef: React.RefObject<HTMLInputElement>,
) => {
  useEffect(() => {
    if (!lockChat && inputRef.current) {
      inputRef.current.focus();
    }
  }, [lockChat, inputRef]);

  return inputRef;
};

export default useFocusOnUnlock;
