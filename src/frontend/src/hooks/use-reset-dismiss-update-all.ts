import { useEffect } from "react";
import { useUtilityStore } from "../stores/utilityStore";
export const useResetDismissUpdateAll = () => {
  const setDismissAll = useUtilityStore((state) => state.setDismissAll);

  useEffect(() => {
    setDismissAll(false);
  }, []);
};
