import React from "react";
import Code from "@theme-original/MDXComponents/Code";
import CodeInline from "@theme/CodeInline";

export default function CodeWrapper(props) {
  const hasWbr = React.Children.toArray(props.children).some((child) => child.type === "wbr");
  return hasWbr ? <CodeInline {...props} /> : <Code {...props} />;
}
