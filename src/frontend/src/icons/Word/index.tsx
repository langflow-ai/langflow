import React, { forwardRef } from "react";
import { ReactComponent as WordSVG } from "./word.svg";

export const WordIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <WordSVG ref={ref} {...props} />;
  }
);
