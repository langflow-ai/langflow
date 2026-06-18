import React, { forwardRef } from "react";
import logo from "./dataforb2b_logo.png";

const SvgDataForB2B = forwardRef((props, ref) => (
  <img
    ref={ref}
    src={logo}
    alt="DataForB2B"
    style={{ width: "100%", height: "100%", objectFit: "contain" }}
    {...props}
  />
));

SvgDataForB2B.displayName = "SvgDataForB2B";

export default SvgDataForB2B;
