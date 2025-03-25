import React, { forwardRef } from "react";
import GmailIconSVG from "./gmail";

export const GmailIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <GmailIconSVG ref={ref} {...props} />;
  },
);
