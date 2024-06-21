import React, { forwardRef } from "react";
import SvgFacebookMessengerLogo2020 from "./FacebookMessengerLogo2020";

export const FBIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgFacebookMessengerLogo2020 ref={ref} {...props} />;
  },
);
