import type React from "react";
import { forwardRef } from "react";
import SvgGetYouTubeTranscript from "./GetYouTubeTranscriptIcon";

export const GetYouTubeTranscriptIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & { isDark?: boolean }
>((props, ref) => {
  return <SvgGetYouTubeTranscript ref={ref} {...props} />;
});
