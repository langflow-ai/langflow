import type React from "react";
import { forwardRef } from "react";
import { AIMLComponent } from "./AI-ML";

export const AIMLIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <AIMLComponent ref={ref} {...props} />;
  },
);
