import React, { useEffect, useRef, useState } from "react";
import { cn } from "../../utils/utils";

const DynamicLineClamp = ({ children, initial, className }) => {
  const [lineClamp, setLineClamp] = useState(initial);
  const parentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const updateLineClamp = () => {
      if (parentRef.current) {
        const parentHeight = parentRef.current.clientHeight;
        const lineHeight = parseFloat(
          getComputedStyle(parentRef.current).lineHeight,
        );
        const lines = Math.floor(parentHeight / lineHeight);
        setLineClamp(lines);
      }
    };

    updateLineClamp();
    window.addEventListener("resize", updateLineClamp);

    return () => {
      window.removeEventListener("resize", updateLineClamp);
    };
  }, []);

  return (
    <div ref={parentRef} className="relative">
      <span className={cn(`line-clamp-${lineClamp}`, className)}>
        {children}
      </span>
    </div>
  );
};

export default DynamicLineClamp;
