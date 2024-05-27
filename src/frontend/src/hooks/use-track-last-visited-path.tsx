import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useLocationStore } from "../stores/locationStore";

function useTrackLastVisitedPath() {
  const location = useLocation();
  const setHistory = useLocationStore((state) => state.setRouteHistory);

  useEffect(() => {
    setHistory(location.pathname);
  }, [location]);
}

export default useTrackLastVisitedPath;
