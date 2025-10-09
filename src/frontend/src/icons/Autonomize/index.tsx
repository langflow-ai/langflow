import React, { forwardRef } from "react";
import SvgAutonomize from "./Autonomize";

export const AutonomizeIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgAutonomize ref={ref} {...props} />;
  },
);

export default AutonomizeIcon;