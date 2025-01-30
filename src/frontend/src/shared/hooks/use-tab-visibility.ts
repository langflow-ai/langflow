import { useEffect, useState } from "react";

const useTabVisibility = () => {
  const [tabChanged, setTabChanged] = useState(true);

  useEffect(() => {
    const handleVisibilityChange = () => {
      setTabChanged(document.hidden);
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  return tabChanged;
};

export default useTabVisibility;
