import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import SvgAWS from "./AWS";

export const AWSIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    const isdark = useDarkStore((state) => state.dark);
    return <SvgAWS ref={ref} isdark={isdark} {...props} />;
  },
);
