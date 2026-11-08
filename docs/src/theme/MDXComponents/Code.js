import React from "react";
import Code from "@theme-original/MDXComponents/Code";
import CodeInline from "@theme/CodeInline";

// Docusaurus renders <code> as a code block unless every child is a string.
// rehypeWbrUnderscore adds <wbr> children to table-cell code, which must stay inline.
export default function CodeWrapper(props) {
  const hasWbr = React.Children.toArray(props.children).some((child) => child.type === "wbr");
  return hasWbr ? <CodeInline {...props} /> : <Code {...props} />;
}
