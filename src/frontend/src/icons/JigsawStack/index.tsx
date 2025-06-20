import React, { forwardRef } from "react";
import JigsawStackIconSVG from "./JigsawStackIcon";

export const JigsawStackIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement>
>((props, ref) => {
  return <JigsawStackIconSVG ref={ref} {...props} />;
});

JigsawStackIcon.displayName = "JigsawStackIcon";

export default JigsawStackIcon;
