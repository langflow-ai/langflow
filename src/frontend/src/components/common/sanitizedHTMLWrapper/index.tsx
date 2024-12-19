import DOMPurify from "dompurify";
import { forwardRef } from "react";
import { SanitizedHTMLWrapperType } from "../../../types/components";

const SanitizedHTMLWrapper = forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLHeadingElement> & SanitizedHTMLWrapperType
>(({ content, suppressWarning = false, ...props }, ref) => {
  const sanitizedHTML = DOMPurify.sanitize(content);

  return (
    <div
      ref={ref}
      data-testid="edit-prompt-sanitized"
      dangerouslySetInnerHTML={{ __html: sanitizedHTML }}
      suppressContentEditableWarning={suppressWarning}
      {...props}
      className="m-1 w-full"
    />
  );
});

SanitizedHTMLWrapper.displayName = "SanitizedHTMLWrapper";

export default SanitizedHTMLWrapper;
