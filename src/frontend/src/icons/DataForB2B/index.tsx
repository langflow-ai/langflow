import type React from "react";
import { forwardRef } from "react";
import DataForB2BLogo from "./dataforb2b_logo.png";

export const DataForB2BIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <img src={DataForB2BLogo} alt="DataForB2B Logo" {...props} />;
});
