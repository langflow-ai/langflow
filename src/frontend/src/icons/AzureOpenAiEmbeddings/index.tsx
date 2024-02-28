import React, { forwardRef } from "react";
import SvgAzureChatOpenAi from "./AzureChatOpenAi";

export const AzureOpenAiEmbeddingsIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgAzureChatOpenAi ref={ref} {...props} />;
});
