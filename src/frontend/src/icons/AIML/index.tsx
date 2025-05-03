import React, { forwardRef } from "react";
import { AIMLComponent } from "./AI-ML";

export const AIMLIcon = forwardRef<
  SVGSVGElement,
  React.ComponentPropsWithoutRef<typeof AIMLComponent>
>((props, ref) => {
  return <AIMLComponent ref={ref} {...props} />;
});

AIMLIcon.displayName = "AIMLIcon";
