import React, { forwardRef } from "react";
import { ReactComponent as IFixItSVG } from "./ifixit-seeklogo.com.svg";

export const IFixIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <IFixItSVG ref={ref} {...props} />;
  }
);
