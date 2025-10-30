import * as React from "react";

const MOBILE_BREAKPOINT = 768;

export function useIsMobile({ maxWidth }: { maxWidth?: number } = {}) {
  const breakpoint = maxWidth || MOBILE_BREAKPOINT;
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(
    undefined,
  );

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);

    const handleResize = () => {
      setIsMobile(window.innerWidth < breakpoint);
    };

    // Initial check
    handleResize();

    // Add both matchMedia and resize listeners
    mql.addEventListener("change", handleResize);
    window.addEventListener("resize", handleResize);

    return () => {
      mql.removeEventListener("change", handleResize);
      window.removeEventListener("resize", handleResize);
    };
  }, [breakpoint]);

  return !!isMobile;
}
