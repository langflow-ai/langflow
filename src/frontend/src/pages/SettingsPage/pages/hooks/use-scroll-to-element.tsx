import { useEffect } from "react";

const useScrollToElement = (scrollId: string | null | undefined) => {
  useEffect(() => {
    const element = document.getElementById(scrollId ?? "null");
    if (element) {
      // Scroll smoothly to the top of the next section
      element.scrollIntoView({ behavior: "smooth" });
    }
  }, [scrollId]);
};

export default useScrollToElement;
