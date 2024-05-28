import { useEffect } from "react";

const useFocusOnUnlock = (lockChat, inputRef) => {
  useEffect(() => {
    if (!lockChat && inputRef.current) {
      inputRef.current.focus();
    }
  }, [lockChat, inputRef]);

  return inputRef;
};

export default useFocusOnUnlock;
