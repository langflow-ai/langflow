import React, { forwardRef } from "react";
import { ReactComponent as FacebookMessengerSVG } from "./Facebook_Messenger_logo_2020.svg";

export const FBIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <FacebookMessengerSVG ref={ref} {...props} />;
  }
);
