import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useUtilityStore } from "../stores/utilityStore";
export const useResetDismissUpdateAll = () => {
  const location = useLocation();
  const flowLocationPath = location.pathname.includes("flow");
  const setDismissAll = useUtilityStore((state) => state.setDismissAll);

  useEffect(() => {
    if (flowLocationPath) {
      setDismissAll(false);
    }
  }, [location]);
};
