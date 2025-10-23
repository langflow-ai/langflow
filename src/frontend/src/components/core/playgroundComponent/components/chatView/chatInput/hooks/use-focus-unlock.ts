import { useEffect } from "react";

const useFocusOnUnlock = (
  isBuilding: boolean,
  inputRef: React.RefObject<HTMLInputElement>,
) => {
  useEffect(() => {
    if (!isBuilding && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isBuilding, inputRef]);

  return inputRef;
};

export default useFocusOnUnlock;
