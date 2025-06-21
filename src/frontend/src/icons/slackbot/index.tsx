import React, { forwardRef } from "react";
import SlackbotIconSVG from "./slackbot.jsx";

export const SlackbotIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SlackbotIconSVG ref={ref} {...props} />;
});
