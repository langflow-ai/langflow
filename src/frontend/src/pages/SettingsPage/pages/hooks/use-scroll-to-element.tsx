import { useEffect } from "react";

const useScrollToElement = (scrollId, setCurrentFlowId) => {
  useEffect(() => {
    const element = document.getElementById(scrollId ?? "null");
    if (element) {
      // Scroll smoothly to the top of the next section
      element.scrollIntoView({ behavior: "smooth" });
    }
  }, [scrollId]);

  useEffect(() => {
    setCurrentFlowId("");
  }, [setCurrentFlowId]);
};

export default useScrollToElement;
