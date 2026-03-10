import React, { forwardRef } from "react";
import SvgIBM from "./ibm/IBM";
import SvgWatsonxAI from "./watsonx/WatsonxAI";
import WatsonxOrchestrateImage from "./watsonx/watsonxOrchestrate.png";

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

export const WatsonxOrchestrateIcon = (
  props: React.ComponentPropsWithoutRef<"img">,
) => {
  return (
    <img src={WatsonxOrchestrateImage} alt="watsonx Orchestrate" {...props} />
  );
};
