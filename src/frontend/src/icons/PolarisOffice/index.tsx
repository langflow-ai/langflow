import React, { forwardRef } from "react";
import SvgPolarisOfficeLogo from "./PolarisOfficeLogo";

export const PolarisOfficeIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ isDark?: boolean }>
>((props, ref) => {
  return (
    <SvgPolarisOfficeLogo ref={ref} isDark={props.isDark ?? false} {...props} />
  );
});
