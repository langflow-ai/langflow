import type React from "react";
import { forwardRef } from "react";
import SvgApifyLogo from "./Apify";
import ApifyWhiteImage from "./apify_white.png";

export const ApifyIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgApifyLogo ref={ref} {...props} />;
  },
);

export const ApifyWhiteIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <img src={ApifyWhiteImage} alt="Apify White Logo" {...props} />;
});
