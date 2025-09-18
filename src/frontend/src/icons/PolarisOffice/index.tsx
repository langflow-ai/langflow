import React, { forwardRef } from "react";
import SvgPolarisOfficeLogo from "./PolarisOfficeLogo";

export const PolarisOfficeIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgPolarisOfficeLogo ref={ref} {...props} />;
});
