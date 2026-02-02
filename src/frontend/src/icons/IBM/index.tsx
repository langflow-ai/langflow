import React, { forwardRef } from "react";
import SvgIBM from "./ibm/IBM";
import SvgWatsonxAI from "./watsonx/WatsonxAI";

export const WatsonxAiIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgWatsonxAI ref={ref} {...props} />;
});

export const IBMIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return <SvgIBM ref={ref} {...props} />;
  },
);
